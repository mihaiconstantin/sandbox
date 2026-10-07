# Imports.
from __future__ import annotations

from pathlib import Path, PurePosixPath


# Require a nonblank string value.
def _require_nonblank(value: object, field: str) -> str:
    # If the value is not a nonblank string.
    if not isinstance(value, str) or not value.strip():
        # Throw.
        raise ValueError(f"{field} must be a nonblank string.")

    # Return the validated string.
    return value


# Require a `Path` value.
def _require_path(value: object, field: str) -> Path:
    # If the value is not a path.
    if not isinstance(value, Path):
        # Throw.
        raise ValueError(f"{field} must be a path.")

    # If the path has no value.
    if not str(value):
        # Throw.
        raise ValueError(f"{field} must not be empty.")

    # Return the validated path.
    return value
