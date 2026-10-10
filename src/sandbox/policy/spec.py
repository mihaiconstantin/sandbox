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


# Require the declared volumes to be mounted writable at their declared targets.
def _validate_volumes(plan: SandboxPlan, mounts: tuple[MountSpec, ...]) -> None:
    # Index the declarations by physical name and reject ambiguous targets.
    declared: dict[str, str] = {}
    seen_targets: set[str] = set()

    # For each declaration in plan order.
    for declaration in plan.volumes:
        # Normalize the declared target.
        target: str = guest_target_key(declaration.target)

        # Reject two declarations for the same directory.
        if target in seen_targets:
            # Throw.
            raise ConfigurationError("volumes", "Declared volumes must use distinct targets.")

        # Record the declaration.
        seen_targets.add(target)
        declared[declaration.name] = target

    # Track the declared volumes confirmed by the effective mounts.
    mounted: set[str] = set()

    # Validate every named volume mount.
