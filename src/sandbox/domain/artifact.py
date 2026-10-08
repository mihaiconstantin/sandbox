# Imports.
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_nonblank, _require_path


# Represent how an image crosses from the builder to the runtime.
class ArtifactTransport(StrEnum):
    # The image exists in the runtime-visible local image store.
    LOCAL_IMAGE = "local-image"

    # The image is an uncompressed Docker image archive.
    DOCKER_ARCHIVE = "docker-archive"

    # The image is an uncompressed OCI image-layout archive.
    OCI_ARCHIVE = "oci-archive"


# Represent the image reference, platform, and transport a runtime requires.
@dataclass(frozen = True, slots = True)
class ArtifactRequirement:
    # Record the canonical runtime-facing image reference.
    reference: str

    # Record the required platform when the runtime constrains it.
    platform: str | None

    # Record the accepted build transport.
    transport: ArtifactTransport

    def __post_init__(self) -> None:
        # Require a canonical nonblank reference.
        _require_nonblank(self.reference, "ArtifactRequirement.reference")

        # If a platform is required.
        if self.platform is not None:
            # Require a nonblank platform.
            _require_nonblank(self.platform, "ArtifactRequirement.platform")

        # Require the closed neutral transport vocabulary.
        if not isinstance(self.transport, ArtifactTransport):
            # Throw.
            raise ValueError("ArtifactRequirement.transport must be an ArtifactTransport.")


# Represent the typed image preparation result handed to a runtime.
@dataclass(frozen = True, slots = True)
class BuildArtifact:
    # Record the canonical runtime-facing image reference.
    reference: str

    # Record the effective platform when it is known.
    platform: str | None

    # Record the manifest or index digest when it is known.
    digest: str | None

    # Record how the image crosses to the runtime.
    transport: ArtifactTransport

    # Record the operation-scoped archive for archive transports.
    archive_path: Path | None

    # Report whether this call built or pulled the image.
    created: bool

    def __post_init__(self) -> None:
        # Require a canonical nonblank reference.
        _require_nonblank(self.reference, "BuildArtifact.reference")

        # If a platform is reported.
        if self.platform is not None:
            # Require a nonblank platform.
            _require_nonblank(self.platform, "BuildArtifact.platform")

        # If a digest is reported.
        if self.digest is not None:
            # Require a nonblank manifest or index digest.
            _require_nonblank(self.digest, "BuildArtifact.digest")

        # Require the closed neutral transport vocabulary.
        if not isinstance(self.transport, ArtifactTransport):
            # Throw.
            raise ValueError("BuildArtifact.transport must be an ArtifactTransport.")

        # If the transport carries bytes outside the local image store.
        if self.transport is not ArtifactTransport.LOCAL_IMAGE:
            # Require the operation-scoped archive path.
            _require_path(self.archive_path, "BuildArtifact.archive_path")
        # Otherwise a local image cannot carry an archive.
        elif self.archive_path is not None:
            # Throw.
            raise ValueError("BuildArtifact.archive_path must be `None` for a local-image transport.")

        # Require an exact Boolean creation flag.
        if type(self.created) is not bool:
            # Throw.
            raise ValueError("BuildArtifact.created must be a Boolean.")
