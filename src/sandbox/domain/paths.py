# Imports.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_nonblank, _require_path, _require_workspace_target
