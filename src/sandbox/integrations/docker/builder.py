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

    # Select the normalized platform the prepared image must satisfy.
    def _target_platform(
        self,
        requirement: ArtifactRequirement,
        service: ServiceBuild,
        environment: dict[str, str],
    ) -> str | None:
        # Normalize the required platform when the runtime constrains it.
        required: str | None = _normalized_platform(requirement.platform, requirement)

        # Normalize the service platform when Compose resolves one.
        resolved: str | None = _normalized_platform(service.platform, requirement)

        # Reject a requirement that disagrees with an explicit service platform.
        if required is not None and resolved is not None and not _platforms_match(required, resolved):
            # Throw before preparation.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                expected_platform = required,
                actual_platform = resolved,
                detail = "The required platform does not match the resolved service platform.",
            )

        # Prefer the requirement when it is stated.
        if required is not None:
            # Select the requirement and make Compose honor it when the service is silent.
            if resolved is None:
                # Apply the platform to the Compose build and pull environment.
                environment["DOCKER_DEFAULT_PLATFORM"] = required

            # Return the required platform.
            return required

        # Otherwise use the service platform.
        return resolved

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


# Report whether two normalized platforms describe the same OS and architecture.
def _platforms_match(expected: str, actual: str) -> bool:
    # Split both platform strings.
    expected_parts: list[str] = expected.split("/")
    actual_parts: list[str] = actual.split("/")

    # Require the operating system and architecture to agree.
    if len(expected_parts) < 2 or len(actual_parts) < 2:
        # Treat an incomplete platform as a mismatch.
        return False

    # Compare the operating system and architecture.
    if expected_parts[0] != actual_parts[0] or expected_parts[1] != actual_parts[1]:
        # Report a mismatch.
        return False

    # When both sides name a variant, require it to agree.
    if len(expected_parts) >= 3 and len(actual_parts) >= 3 and expected_parts[2] != actual_parts[2]:
        # Report a variant mismatch.
        return False

    # Report a matching platform.
    return True


# Normalize the registry, repository, tag, and digest for comparison only.
def _reference_key(reference: str) -> str:
    # Strip surrounding whitespace.
    value: str = reference.strip()

    # Reject references that cannot be Docker image references.
    if not value or any(character.isspace() for character in value) or "://" in value:
        # Throw.
        raise ValueError(f"Invalid image reference `{reference}`.")

    # Split a digest when present.
    if "@" in value:
        # Split the repository and digest.
        repository, digest = value.rsplit("@", 1)

        # Return the normalized repository and digest.
        return f"{_repository_key(repository)}@{digest}"

    # Split a tag from the repository.
    repository, tag = _split_tag(value)

    # Return the normalized repository and effective tag.
    return f"{_repository_key(repository)}:{tag or 'latest'}"


# Read a repository and tag from one image reference.
def _split_tag(value: str) -> tuple[str, str | None]:
    # Find the last path separator so a registry port is not mistaken for a tag.
    slash: int = value.rfind("/")
    colon: int = value.rfind(":")

    # Only a colon after the final slash names a tag.
    if colon > slash:
        # Return the repository and tag.
        return value[:colon], value[colon + 1:]

    # Return the repository without a tag.
    return value, None


# Normalize a repository alias for comparison only.
def _repository_key(repository: str) -> str:
    # Normalize the registry aliases Docker accepts.
    value: str = repository.strip().lower()
    for prefix in ("index.docker.io/", "registry-1.docker.io/"):
        # Replace the alias with the canonical registry name.
        if value.startswith(prefix):
            # Normalize the prefix.
            value = "docker.io/" + value[len(prefix):]
            break

    # Drop the implicit Docker Hub library namespace.
    for prefix in ("docker.io/library/", "docker.io/", "library/"):
        # Remove the implicit prefix.
        if value.startswith(prefix):
            # Strip the prefix.
            value = value[len(prefix):]
            break

    # Return the comparison key.
    return value
