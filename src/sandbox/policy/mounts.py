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
