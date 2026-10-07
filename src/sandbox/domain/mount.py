# Imports.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank
