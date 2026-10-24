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

    # Ensure the required image exists and return the typed artifact.
    def prepare(
        self,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        *,
        rebuild: bool = False,
        staging_dir: Path | None = None,
        output: OutputSink = SILENT,
    ) -> BuildArtifact:
        # Require the neutral request values.
        if not isinstance(requirement, ArtifactRequirement):
            # Throw.
            raise ValueError("requirement must be an ArtifactRequirement.")
        if type(rebuild) is not bool:
            # Throw.
            raise ValueError("rebuild must be a Boolean.")
        if staging_dir is not None and not isinstance(staging_dir, Path):
            # Throw.
            raise ValueError("staging_dir must be a path or `None`.")

        # Reject an unimplemented transport before probing or preparing any image.
        self._require_supported_transport(requirement)

        # Require a canonical runtime-facing reference before any engine call.
        try:
            # Validate the reference syntax without rewriting the requested value.
            _reference_key(requirement.reference)

        # Translate an invalid reference into the typed artifact rejection.
        except ValueError as error:
            # Throw.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                detail = "The image reference is not canonical.",
            ) from error

        # Require operation-scoped staging before any image preparation for an archive.
        archive: bool = requirement.transport is ArtifactTransport.DOCKER_ARCHIVE
        if archive:
            # Reject a missing or unusable staging directory before the engine runs.
            self._require_staging(staging_dir)

        # Prepare the Compose interpolation environment without mutating process state.
        project_directory: Path = plan.project.directory.expanduser().resolve(strict = False)
        environment: dict[str, str] = compose_environment(plan.project.name, project_directory)

        # Make Compose honor an explicitly required platform even when the service omits one.
        if requirement.platform is not None:
            # Apply the platform to every build and pull in this preparation.
            environment["DOCKER_DEFAULT_PLATFORM"] = requirement.platform

        # Require the supported Compose floor before resolving the recipe.
        require_compose(self._compose, operation = "prepare")

        # Resolve the effective service read-only.
        configuration: Mapping[str, Any] = self._compose.configuration(definition, definition.files, environment)
        service: ServiceBuild = project_service(
            configuration,
            plan,
            definition,
            default_platform = environment.get("DOCKER_DEFAULT_PLATFORM") or None,
        )

        # Require the resolved service image to satisfy the requested reference.
        if not _same_reference(service.image, requirement.reference):
            # Throw the artifact rejection before touching the image store.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                detail = f"The resolved service image `{service.image}` does not match the required reference.",
            )

        # Resolve the target platform from the requirement, the service, and the environment.
        target_platform: str | None = self._target_platform(requirement, service, environment)

        # Ensure the image exists with the intended build, pull, or reuse semantics.
        created: bool = self._ensure_image(
            requirement = requirement,
            service = service,
            definition = definition,
            environment = environment,
            platform = target_platform,
            rebuild = rebuild,
            output = output,
        )

        # Return the local image artifact with an optional manifest digest.
        if not archive:
            # Inspect the prepared image for a portable manifest digest.
            inspection: Mapping[str, Any] = self._docker.inspect_image(
                service.image,
                platform = target_platform,
                operation = "inspect",
            )

            # Return the local-image artifact.
            return BuildArtifact(
                reference = requirement.reference,
                platform = requirement.platform,
                digest = _manifest_digest(inspection, service.image),
                transport = ArtifactTransport.LOCAL_IMAGE,
                archive_path = None,
                created = created,
            )

        # Inspect the image before export to prove its architecture.
        inspection = self._docker.inspect_image(service.image, platform = target_platform, operation = "inspect")

        # Read the actual image platform from Docker's own facts.
        actual_platform: str | None = self._docker.image_platform(inspection)

        # Require an inspectable architecture before writing an archive.
        if actual_platform is None:
            # Throw.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                expected_platform = requirement.platform,
                detail = "Cannot determine the image platform before archive export.",
            )

        # Validate the target architecture before export.
        if target_platform is not None:
            # Compare the requested platform with the image's own platform.
            if not _platforms_match(target_platform, actual_platform):
                # Throw before any export mutation.
                raise ArtifactRejected(
                    transport = requirement.transport.value,
                    reference = requirement.reference,
                    expected_platform = target_platform,
                    actual_platform = actual_platform,
                    detail = "The prepared image does not match the required platform.",
                )

        # Export through the platform selected by the requirement or the image itself.
        export_platform: str = target_platform or actual_platform

        # Return the single-image archive.
        return self._export_archive(requirement, service, export_platform, staging_dir, created)

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

    # Export exactly one target image into an uncompressed Docker archive.
    def _export_archive(
        self,
        requirement: ArtifactRequirement,
        service: ServiceBuild,
        platform: str | None,
        staging_dir: Path | None,
        created: bool,
    ) -> BuildArtifact:
        # Rerequire the caller-owned staging directory for the type checker.
        assert staging_dir is not None

        # Prepare the operation-scoped archive path.
        destination: Path = staging_dir / ARCHIVE_NAME

        # Translate any operation-scoped filesystem failure without leaking an OS exception.
        try:
            # Write into a temporary directory so a failed export leaves no partial artifact.
            with _export_staging(staging_dir) as temporary:
                # Write the transient archive.
                candidate: Path = temporary / ARCHIVE_NAME

                # Export exactly one image for the effective platform.
                result: CommandResult = self._docker.save_image(
                    service.image,
                    platform = platform,
                    destination = candidate,
                    operation = "export",
                )

                # Translate a failed export with its command facts.
                if result.returncode != 0:
                    # Throw the typed build failure.
                    raise BuildFailed(self._docker.failure("export", result.arguments, result))

                # Prove the archive is an uncompressed, single-image Docker archive.
                _validate_archive(candidate, requirement.reference, service.image)

                # Publish the validated archive into the operation-scoped staging directory.
                os.replace(candidate, destination)

        # Translate a staging filesystem failure once.
        except OSError as error:
            # Throw the typed artifact rejection.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                detail = f"The image archive could not be written: {error}",
            ) from error

        # Return the archive artifact; created reflects build/pull, not export.
        return BuildArtifact(
            reference = requirement.reference,
            platform = requirement.platform,
            digest = None,
            transport = ArtifactTransport.DOCKER_ARCHIVE,
            archive_path = destination,
            created = created,
        )


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


# Report whether two references denote the same Docker image.
def _same_reference(left: str, right: str) -> bool:
    # Compare canonicalized references without inventing a new artifact string.
    try:
        # Normalize both sides for comparison.
        return _reference_key(left) == _reference_key(right)

    # Treat an invalid reference as a non-match.
    except ValueError:
        # Report a mismatch.
        return False


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


# Read a manifest digest from Docker's repository digests, never its config ID.
def _manifest_digest(inspection: Mapping[str, Any], reference: str) -> str | None:
    # Read the repository digests reported by Docker.
    digests: Any = inspection.get("RepoDigests")

    # Report no digest when Docker has no repository digest.
    if not isinstance(digests, list):
        # Return no digest.
        return None

    # Read the reference repository without a tag or digest for comparison.
    repository_value: str = reference.split("@", 1)[0]
    repository: str = _repository_key(_split_tag(repository_value)[0])

    # Find the first repository digest for this image.
    for entry in digests:
        # Require a string `repo@digest` entry.
        if not isinstance(entry, str) or "@" not in entry:
            # Skip malformed entries.
            continue

        # Split the repository and digest.
        entry_repository, digest = entry.rsplit("@", 1)

        # Compare the repository without tags.
        if _repository_key(_split_tag(entry_repository)[0]) != repository:
            # Skip a digest for another repository.
            continue

        # Require a nonblank digest value.
        if digest.strip():
            # Return the manifest or index digest.
            return digest.strip()

    # Never fall back to Docker's config `Id`.
    return None


# Validate one uncompressed Docker archive with exactly one target image.
def _validate_archive(path: Path, reference: str, service_image: str) -> None:
    # Parse the archive with the uncompressed reader.
    try:
        # Open the uncompressed outer tar.
        with tarfile.open(path, mode = "r:") as archive:
            # Read the Docker archive manifest.
            member: tarfile.TarInfo = archive.getmember(ARCHIVE_MANIFEST)
            extracted: Any = archive.extractfile(member)

            # Require a readable manifest member.
            if extracted is None:
                # Throw into the shared translation.
                raise ValueError("The Docker archive has no readable manifest.")

            # Parse the manifest JSON.
            payload: Any = json.loads(extracted.read())

    # Translate every malformed-archive failure into one typed rejection.
    except (tarfile.TarError, KeyError, ValueError, OSError) as error:
        # Throw the typed artifact rejection.
        raise ArtifactRejected(
            transport = ArtifactTransport.DOCKER_ARCHIVE.value,
            reference = reference,
            detail = "The exported image archive is not an uncompressed Docker image archive.",
        ) from error

    # Require exactly one image entry in the archive.
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], Mapping):
        # Throw.
        raise ArtifactRejected(
            transport = ArtifactTransport.DOCKER_ARCHIVE.value,
            reference = reference,
            detail = "The Docker archive must contain exactly one target image.",
        )

    # Read the manifest tags.
    tags: Any = payload[0].get("RepoTags")

    # Require a canonical tag for the target image.
    if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) for tag in tags):
        # Throw.
        raise ArtifactRejected(
            transport = ArtifactTransport.DOCKER_ARCHIVE.value,
            reference = reference,
            detail = "The Docker archive must carry exactly one tagged target image.",
        )

    # Require the manifest to name the target image.
    if not any(_same_reference(tag, reference) or _same_reference(tag, service_image) for tag in tags):
        # Throw.
        raise ArtifactRejected(
            transport = ArtifactTransport.DOCKER_ARCHIVE.value,
            reference = reference,
            detail = "The Docker archive does not contain the required target image.",
        )
