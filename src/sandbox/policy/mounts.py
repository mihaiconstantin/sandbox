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
    for index, mount in enumerate(mounts):
        # Require a neutral mount declaration.
        if not isinstance(mount, MountSpec):
            # Throw.
            raise ConfigurationError(f"mounts[{index}]", "Must be a MountSpec value.")

        # Normalize the guest target for collision checks.
        target: str = guest_target_key(mount.target)

        # If two mounts claim the same guest target, reject the ambiguity.
        if target in seen_targets:
            # Throw.
            raise ConfigurationError(f"mounts[{index}].target", "Mount targets must be unique.")

        # Record the target before validating the source.
        seen_targets.add(target)

        # If the mount is a host bind.
        if mount.kind == "bind":
            # Require an absolute host path from the neutral declaration.
            if not isinstance(mount.source, Path):
                # Throw.
                raise ConfigurationError(f"mounts[{index}].source", "Must be an absolute host path.")

            # Resolve the source for containment and identity checks.
            source: Path = _resolved(mount.source)

            # Reject the Docker socket by name even inside an otherwise allowed root.
            if source.name == DOCKER_SOCKET:
                # Throw.
                raise ConfigurationError(f"mounts[{index}].source", "Docker socket mounts are not allowed.")

            # Require containment in the project or catalogue directory.
            contained: bool = source.is_relative_to(project_dir) or (catalogue_dir is not None and source.is_relative_to(catalogue_dir))
            if not contained:
                # Throw.
                raise ConfigurationError(f"mounts[{index}].source", "Bind mounts must remain inside the project or catalogue directory.")

            # If the mount uses the fixed project target, require the project directory source.
            if target == expected_target:
                # If the project bind uses another source.
                if source != project_dir:
                    # Throw.
                    raise ConfigurationError(f"mounts[{index}].source", "The project mount must use the project directory as its source.")

                # Count the project mount.
                project_mounts += 1

            # Continue to the next mount.
            continue

        # Require a physical volume name from the neutral declaration.
        if not isinstance(mount.source, str) or not mount.source.strip():
            # Throw.
            raise ConfigurationError(f"mounts[{index}].source", "Must be a nonblank physical volume name.")

        # A named volume cannot stand in for the project bind.
        if target == expected_target:
            # Throw.
            raise ConfigurationError(f"mounts[{index}].kind", "The project mount must be a bind mount.")

    # Require exactly one project bind at the fixed target.
    if project_mounts != 1:
        # Throw.
        raise ConfigurationError("mounts", f"Must contain exactly one project bind at `{expected_target}`.")


# Derive the read-only secret file deliveries for a plan.
def secret_deliveries(plan: SandboxPlan) -> tuple[MountSpec, ...]:
    # Derive one fixed read-only delivery per bound secret.
    return tuple(
        MountSpec(kind = "bind", source = secret.host_path, target = secret_target(secret.alias), read_only = True)
        for secret in plan.secrets
    )
