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
