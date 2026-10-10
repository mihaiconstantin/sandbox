# Imports.
from __future__ import annotations

from pathlib import Path

# Import the neutral mount and plan values.
from sandbox.domain import SECRET_ROOT, MountSpec, SandboxPlan, secret_target
from sandbox.domain.paths import guest_target_key

# Import the typed configuration error.
from sandbox.errors.configuration import ConfigurationError

# The Docker socket filename rejected by the security policy.
DOCKER_SOCKET: str = "docker.sock"


# Resolve one host path without requiring it to exist.
def _resolved(path: Path) -> Path:
    # Expand and resolve the path for containment checks.
    return path.expanduser().resolve(strict = False)


# Validate the neutral mount envelope for one effective sandbox.
def validate_mounts(plan: SandboxPlan, mounts: tuple[MountSpec, ...], catalogue_root: Path | None = None) -> None:
    # Resolve the project root and the optional catalogue root once.
    project_dir: Path = _resolved(plan.project.directory)
    catalogue_dir: Path | None = None if catalogue_root is None else _resolved(catalogue_root)

    # Record the fixed project target.
    expected_target: str = guest_target_key(plan.workspace.target)

    # Track duplicate targets and the required project bind.
    seen_targets: set[str] = set()
    project_mounts: int = 0

    # Validate every mount in declaration order.
