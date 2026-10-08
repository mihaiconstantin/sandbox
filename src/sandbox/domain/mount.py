# Imports.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank


# Represent an observed attachment of storage to a sandbox.
@dataclass(frozen = True)
class Mount:
    # Record whether the source is a host bind or a physical volume.
    kind: Literal["bind", "volume"]

    # Record the host path or physical volume name.
    source: str

    # Record the guest target.
    target: str

    def __post_init__(self) -> None:
        # Require a supported mount kind.
        if self.kind not in ("bind", "volume"):
            # Throw.
            raise ValueError("Mount.kind must be `bind` or `volume`.")

        # Require a source and an absolute guest target.
        _require_nonblank(self.source, "Mount.source")
        _require_guest_path(self.target, "Mount.target")


# Represent an observed network attachment.
@dataclass(frozen = True)
class Network:
    # Record the network name.
    name: str

    # Record the assigned address, or an empty string when unassigned.
    ip_address: str

    def __post_init__(self) -> None:
        # Require a network name and a string address.
        _require_nonblank(self.name, "Network.name")

        # If the address is not a string.
        if not isinstance(self.ip_address, str):
            # Throw.
            raise ValueError("Network.ip_address must be a string.")


# Represent the neutral declaration of one effective mount before a create.
@dataclass(frozen = True, slots = True)
class MountSpec:
    # Record whether the source is a host bind or a physical volume.
    kind: Literal["bind", "volume"]

    # Record the absolute host path or physical volume name.
    source: Path | str

    # Record the guest target.
    target: str

    # Record whether the mount is read-only.
    read_only: bool

    def __post_init__(self) -> None:
        # Require a supported mount kind.
        if self.kind not in ("bind", "volume"):
            # Throw.
            raise ValueError("MountSpec.kind must be `bind` or `volume`.")

        # If the source is a host path.
        if isinstance(self.source, Path):
            # Require an absolute host path.
            if not self.source.is_absolute():
                # Throw.
                raise ValueError("MountSpec.source must be an absolute host path or a physical volume name.")
        # Otherwise require a physical volume name.
        else:
            # Require a nonblank string source.
            _require_nonblank(self.source, "MountSpec.source")

        # Require an absolute guest target.
        _require_guest_path(self.target, "MountSpec.target")

        # Require an exact Boolean read-only flag.
        if type(self.read_only) is not bool:
            # Throw.
            raise ValueError("MountSpec.read_only must be a Boolean.")


# Export the neutral mount values.
__all__: list[str] = ["Mount", "MountSpec", "Network"]
