# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank

# Import the observed runtime reference.
from sandbox.domain.observation import RuntimeRef


# Represent the catalogue's statement of a shared volume.
@dataclass(frozen = True)
class VolumeDeclaration:
    # Identify the physical runtime volume.
    name: str

    # Record the supported storage scope.
    scope: str

    # Record the guest mount target.
    target: str

    def __post_init__(self) -> None:
        # Require a Docker-compatible physical name.
        _require_nonblank(self.name, "VolumeDeclaration.name")

        # If the volume name is invalid.
        if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+", self.name) is None:
            # Throw.
            raise ValueError("VolumeDeclaration.name must be a Docker volume name of at least two characters, starting with a letter or digit and containing only letters, digits, periods, hyphens, or underscores.")

        # Only `shared` storage exists in this version.
        if self.scope != "shared":
            # Throw.
            raise ValueError("VolumeDeclaration.scope must be `shared`.")

        # Require a literal absolute guest target without interpolation.
        _require_guest_path(self.target, "VolumeDeclaration.target")

        # If the target still contains an interpolation sigil.
        if "$" in self.target:
            # Throw.
            raise ValueError("VolumeDeclaration.target must be a literal guest path without dollar signs.")


# Represent the runtime's report of a shared volume.
@dataclass(frozen = True)
class VolumeInfo:
    # Identify the physical runtime volume.
    name: str

    # Report the driver when available.
    driver: str | None

    # Report the display mountpoint when available.
    mountpoint: str | None

    # Report the referencing runtime instances, or `None` when unavailable.
    in_use_by: tuple[RuntimeRef, ...] | None

    def __post_init__(self) -> None:
        # Require a physical volume name.
        _require_nonblank(self.name, "VolumeInfo.name")

        # If a driver is reported.
        if self.driver is not None:
            # Require a nonblank driver name.
            _require_nonblank(self.driver, "VolumeInfo.driver")

        # If a mountpoint is reported.
        if self.mountpoint is not None:
            # Require a nonblank display path.
            _require_nonblank(self.mountpoint, "VolumeInfo.mountpoint")

        # If references are reported.
        if self.in_use_by is not None:
            # Require an immutable tuple of runtime references.
            if not isinstance(self.in_use_by, tuple) or any(not isinstance(reference, RuntimeRef) for reference in self.in_use_by):
                # Throw.
                raise ValueError("VolumeInfo.in_use_by must be `None` or a tuple of RuntimeRef values.")
