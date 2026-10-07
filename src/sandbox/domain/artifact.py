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
