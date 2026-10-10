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
    for mount in mounts:
        # Skip host binds; they are validated by the mount policy.
        if mount.kind != "volume":
            # Continue to the next mount.
            continue

        # Require a physical volume name from the mount.
        source: Path | str = mount.source
        if not isinstance(source, str):
            # Throw.
            raise ConfigurationError("volumes", "Named volume mounts must use a physical volume name.")

        # If the volume is not declared by the plan.
        if source not in declared:
            # Throw.
            raise ConfigurationError("volumes", "Named volumes must be declared by the plan.")

        # If the mount does not use the declared target.
        if guest_target_key(mount.target) != declared[source]:
            # Throw.
            raise ConfigurationError("volumes", "Declared volumes must be mounted at their declared targets.")

        # Initialization must not be bypassed by a read-only declared volume.
        if mount.read_only:
            # Throw.
            raise ConfigurationError("volumes", "Declared persistent volumes must be writable.")

        # Record the confirmed volume.
        mounted.add(source)

    # Require every declared volume to be present.
    for name in declared:
        # If the declaration has no effective mount.
        if name not in mounted:
            # Throw.
            raise ConfigurationError("volumes", "Every declared volume must be mounted.")


# Validate a plan and its effective neutral spec.
def validate_spec(plan: SandboxPlan, spec: SandboxSpec, *, catalogue_root: Path | None = None) -> None:
    # Require the plan workspace to describe the project directory at the fixed target.
    if plan.workspace.host_directory != plan.project.directory or plan.workspace.target != project_target(plan.project.name):
        # Throw.
        raise ConfigurationError("workspace", "The workspace must bind the project directory at the fixed project target.")

    # Require the fixed working directory.
    if spec.working_directory != plan.workspace.target:
        # Throw.
        raise ConfigurationError("working_directory", f"Must be `{plan.workspace.target}`.")

    # Apply the root policy to the explicit service user.
    _validate_user(spec.user, plan.allow_root, spec.image)

    # Reject privileged execution.
    if spec.privileged:
        # Throw.
        raise ConfigurationError("privileged", "Privileged sandboxes are not allowed.")

    # Reject host networking.
    if spec.host_network:
        # Throw.
        raise ConfigurationError("host_network", "Host networking is not allowed.")

    # Require secret files to stay outside the recipe mount set before containment checks.
    validate_secret_deliveries(plan, spec.mounts)

    # Validate mount containment, uniqueness, and the project bind.
    validate_mounts(plan, spec.mounts, catalogue_root)

    # Validate the declared volumes and their effective mounts.
    _validate_volumes(plan, spec.mounts)
