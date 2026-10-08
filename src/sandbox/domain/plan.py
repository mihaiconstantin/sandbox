# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank, _require_path
from sandbox.domain.paths import PROJECT_ROOT, Workspace
from sandbox.domain.volume import VolumeDeclaration


# Represent a named binding between a project name and a host directory.
@dataclass(frozen = True)
class Project:
    # Identify the project and its box.
    name: str

    # Record the immutable host project directory.
    directory: Path

    def __post_init__(self) -> None:
        # Require a nonblank project name and a host directory.
        _require_nonblank(self.name, "Project.name")
        _require_path(self.directory, "Project.directory")
