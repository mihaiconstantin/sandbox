# Imports.
from __future__ import annotations

# Import the neutral initialization, mount, and plan values.
from sandbox.domain import Initialization, MountSpec, SandboxPlan

# Import the typed configuration errors.
from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed

# Import the shared target comparison rule.
from sandbox.domain.paths import guest_target_key


# Validate the effective initialization against the plan and its mounts.
def validate_initialization(plan: SandboxPlan, initialization: Initialization, mounts: tuple[MountSpec, ...] | None = None) -> None:
    # Apply the root policy to the effective UID on every create path.
    if initialization.uid == 0 and not plan.allow_root:
        # Throw the typed root-policy error.
        raise RootExecutionNotAllowed(uid = 0, source = "initialization")

    # Collect the declared volume targets.
    declared_targets: set[str] = {guest_target_key(declaration.target) for declaration in plan.volumes}

    # Collect the writable volume targets from the effective mounts, or trust the declarations.
    writable_targets: set[str] = (
        {guest_target_key(mount.target) for mount in mounts if mount.kind == "volume" and not mount.read_only}
        if mounts is not None
        else set(declared_targets)
    )

    # Require every target to be a declared, writable volume mount.
    for target in initialization.targets:
        # Normalize the planned target.
        key: str = guest_target_key(target)

        # If the target is not declared or not writable.
        if key not in declared_targets or key not in writable_targets:
            # Throw.
            raise ConfigurationError("initialization.targets", "Initialization targets must be declared, writable volume mounts.")
