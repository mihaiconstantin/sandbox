# Imports.
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Import the shared invariant helper and fixed project root.
from sandbox.domain._invariants import _require_nonblank
from sandbox.domain.mount import Mount, Network
from sandbox.domain.paths import PROJECT_ROOT, Workspace
