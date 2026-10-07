# Imports.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_nonblank, _require_path, _require_workspace_target

# The container directory containing project bind mounts.
PROJECT_ROOT: str = "/projects"

# The container directory containing secret bind mounts.
SECRET_ROOT: str = "/run/secrets"


# Compute the container directory associated with a project.
def project_target(project: str) -> str:
    # Require a project name.
    _require_nonblank(project, "project")

    # Return the project mount target inside the box.
    return f"{PROJECT_ROOT}/{project}"


# Compute the container path associated with a secret alias.
def secret_target(alias: str) -> str:
    # Require a secret alias.
    _require_nonblank(alias, "alias")

    # Return the secret mount target inside the box.
    return f"{SECRET_ROOT}/{alias}"
