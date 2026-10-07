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


# Require an absolute normalized POSIX guest path.
def _require_guest_path(value: object, field: str) -> str:
    # Require a nonblank string value first.
    value = _require_nonblank(value, field)

    # Interpret the value using container rather than host path rules.
    path: PurePosixPath = PurePosixPath(value)

    # If the value is relative, traverses parents, or cannot remain a literal POSIX destination.
    if not path.is_absolute() or ".." in path.parts or "\\" in value or "\x00" in value:
        # Throw.
        raise ValueError(f"{field} must be an absolute POSIX path without parent traversal, backslashes, or NUL bytes.")

    # Return the validated guest path.
    return value


# Require the fixed project target for a box.
def _require_workspace_target(value: object, field: str) -> str:
    # Require an absolute guest path first.
    value = _require_guest_path(value, field)

    # Interpret the target as a container path.
    path: PurePosixPath = PurePosixPath(value)

    # Require the fixed `/projects/<box name>` shape.
    if len(path.parts) != 3 or path.parts[1] != "projects":
        # Throw.
        raise ValueError(f"{field} must be the fixed project target `/projects/<box name>`.")

    # Return the validated target.
    return value


# Define the API of the shared domain invariant helpers.
__all__: list[str] = ["_require_guest_path", "_require_nonblank", "_require_path", "_require_workspace_target"]
