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
