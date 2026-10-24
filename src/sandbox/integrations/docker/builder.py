# Imports.
from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Import the public typed errors raised by the builder.
from sandbox.errors.base import CommandFailure
from sandbox.errors.build import BuildFailed
from sandbox.errors.capabilities import ArtifactRejected
from sandbox.errors.engine import EngineFailure

# Import the neutral port and its values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BuildArtifact,
    RecipeDefinition,
    SandboxPlan,
)
from sandbox.ports.builder import Builder
from sandbox.ports.output import SILENT, OutputSink, ProgressPhase

# Import the ordinary helper values.
from sandbox.integrations.docker.build_contract import ServiceBuild, project_service
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.compose_cli import ComposeCli
from sandbox.integrations.docker.invocation import compose_environment
from sandbox.integrations.docker.preflight import require_buildx, require_compose

# Name the single archive produced for one operation.
ARCHIVE_NAME: str = "artifact.tar"

# Name the single image manifest inside a Docker archive.
ARCHIVE_MANIFEST: str = "manifest.json"


# Prepare Docker images and typed artifacts for a runtime requirement.
class DockerBuilder(Builder):
    # Construct the builder around one Docker gateway.
    def __init__(self, docker: DockerCli) -> None:
        # Record the shared gateway and its Compose facade.
        self._docker: DockerCli = docker
        self._compose: ComposeCli = ComposeCli(docker)

    # Reject transports the Docker builder does not implement before any work.
    def _require_supported_transport(self, requirement: ArtifactRequirement) -> None:
        # OCI archives remain a future transport.
        if requirement.transport is ArtifactTransport.OCI_ARCHIVE:
            # Throw before building.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                detail = "OCI archives are not implemented by the Docker builder.",
            )

    # Require an existing caller-owned staging directory for an archive.
    def _require_staging(self, staging_dir: Path | None) -> None:
        # Require the operation-scoped staging directory.
        if staging_dir is None:
            # Throw before any image preparation.
            raise ValueError("Archive transports require a staging directory.")

        # Require an existing directory rather than creating caller-owned state.
        if not staging_dir.is_dir():
            # Throw.
            raise ValueError("staging_dir must reference an existing directory.")

    # Ensure the image exists through reuse, a build, or a pull.
    def _ensure_image(
        self,
        *,
        requirement: ArtifactRequirement,
        service: ServiceBuild,
        definition: RecipeDefinition,
        environment: Mapping[str, str],
        platform: str | None,
        rebuild: bool,
        output: OutputSink,
    ) -> bool:
        # Check the local image for the effective platform.
        present: bool = self._docker.image_exists(service.image, platform = platform, operation = "prepare")

        # A service that declares a build uses the selected build policy.
        if service.build is not None:
            # Reuse a present image unless an explicit rebuild was requested.
            if present and not rebuild:
                # Report reuse rather than creation.
                return False

            # Require Buildx only when a build will actually run.
            require_buildx(self._docker, operation = "build")

            # Announce only the actual build, never a pull or reuse.
            output.progress(ProgressPhase.BUILD_IMAGE, subject = definition.service)

            # Run the build graph for the selected service and its dependencies.
            result: CommandResult = self._compose.build(
                definition,
                definition.files,
                definition.service,
                environment,
                output,
            )

            # Translate a failed build with its command facts.
            if result.returncode != 0:
                # Throw the typed build failure.
                raise BuildFailed(self._docker.failure("build", result.arguments, result))

            # Require the build to leave the required image available.
            if not self._docker.image_exists(service.image, platform = platform, operation = "prepare"):
                # Throw a typed post-build failure.
                raise BuildFailed(
                    CommandFailure(
                        backend = "docker",
                        operation = "build",
                        command = result.arguments,
                        exit_code = 1,
                        diagnostic = f"The build completed without producing image `{service.image}`.",
                    )
                )

            # Report the build as this call's creation.
            return True

        # An image-only service reuses a present image even when a rebuild was requested.
        if present:
            # Report reuse rather than creation.
            return False

        # Pull the missing image with streamed progress.
        result = self._docker.pull_image(
            service.image,
            platform = platform,
            operation = "pull",
            environment = environment,
            output = output,
        )

        # Translate a failed pull with its command facts.
        if result.returncode != 0:
            # Throw the neutral engine failure.
            raise EngineFailure(self._docker.failure("pull", result.arguments, result))

        # Require the pull to leave the required image available.
        if not self._docker.image_exists(service.image, platform = platform, operation = "prepare"):
            # Throw a typed post-pull failure.
            raise EngineFailure(
                CommandFailure(
                    backend = "docker",
                    operation = "pull",
                    command = result.arguments,
                    exit_code = 1,
                    diagnostic = f"The pull completed without producing image `{service.image}`.",
                )
            )

        # Report the pull as this call's creation.
        return True


# Create a transient export directory under the operation-owned staging root.
@contextmanager
def _export_staging(root: Path) -> Generator[Path, None, None]:
    # Allocate a unique working directory inside the operation scope.
    temporary: Path = Path(tempfile.mkdtemp(prefix = ".sb-export-", dir = root))

    # Always remove the transient export directory.
    try:
        # Yield the operation-scoped working directory.
        yield temporary

    # Clean up even when the export or validation fails.
    finally:
        # Remove the transient directory and every partial file.
        shutil.rmtree(temporary, ignore_errors = True)


# Normalize a platform into `os/arch[/variant]` and reject malformed values.
def _normalized_platform(value: str | None, requirement: ArtifactRequirement) -> str | None:
    # Preserve an unspecified platform.
    if value is None:
        # Return no platform.
        return None

    # Split the platform components.
    parts: list[str] = [part.strip().lower() for part in value.split("/")]

    # Default a single component to Linux.
    if len(parts) == 1:
        # Prepend the standard operating system.
        parts = ["linux", parts[0]]

    # Require the normalized `os/arch[/variant]` form.
    if len(parts) > 3 or any(not part or any(character.isspace() for character in part) for part in parts):
        # Throw a typed artifact rejection for a malformed requirement.
        raise ArtifactRejected(
            transport = requirement.transport.value,
            reference = requirement.reference,
            expected_platform = requirement.platform,
            detail = f"Invalid platform `{value}`.",
        )

    # Return the normalized platform.
    return "/".join(parts)
