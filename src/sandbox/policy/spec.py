# Imports.
from __future__ import annotations

from pathlib import Path

# Import the neutral spec and plan values and the fixed project target helper.
from sandbox.domain import MountSpec, SandboxPlan, SandboxSpec, project_target

# Import the typed configuration errors.
from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed

# Import the mount and secret policy.
from sandbox.domain.paths import guest_target_key
from sandbox.policy.mounts import validate_mounts, validate_secret_deliveries


# Reject explicit root execution unless the plan allows it.
def _validate_user(value: str | int | None, allow_root: bool, image: str) -> None:
    # If the service uses the image default, keep it.
    if value is None:
        # Return without an override.
        return

    # Read the account part of a user specification.
    account: str = str(value).split(":", 1)[0]

    # If root execution is requested without permission.
    if not allow_root and account in ("root", "0"):
        # Throw with the typed root-policy error.
        raise RootExecutionNotAllowed(uid = 0 if account == "0" else None, source = "recipe", image = image)
