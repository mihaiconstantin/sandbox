# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_nonblank, _require_path


# Require a secret alias usable as one file name.
def _require_alias(value: object, field: str) -> str:
    # Require a nonblank alias first.
    value = _require_nonblank(value, field)

    # If the alias contains a path separator, traversal, or unsupported characters.
    if re.fullmatch(r"[A-Za-z0-9._-]+", value) is None or value in (".", ".."):
        # Throw.
        raise ValueError(f"{field} must be one file name containing only letters, digits, periods, hyphens, or underscores.")

    # Return the validated alias.
    return value
