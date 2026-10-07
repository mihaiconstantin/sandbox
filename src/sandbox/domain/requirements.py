# Imports.
from __future__ import annotations

from dataclasses import dataclass

# Import the neutral mount declaration and shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank
from sandbox.domain.mount import MountSpec

# Import the artifact values.
from sandbox.domain.artifact import ArtifactRequirement


# Represent the small neutral set of effective facts a create validates.
@dataclass(frozen = True, slots = True)
class SandboxSpec:
    # Record the effective image reference.
    image: str

    # Record the effective platform when the recipe declares one.
    platform: str | None

    # Record the effective service user when declared.
    user: str | int | None

    # Record the effective working directory.
    working_directory: str | None

    # Record whether privileged mode is effective.
    privileged: bool

    # Record whether host networking is effective.
    host_network: bool

    # Record the effective storage mounts, excluding derived secret files.
    mounts: tuple[MountSpec, ...]

    def __post_init__(self) -> None:
        # Require the effective image identity.
        _require_nonblank(self.image, "SandboxSpec.image")

        # If a platform is reported.
        if self.platform is not None:
            # Require a nonblank platform.
            _require_nonblank(self.platform, "SandboxSpec.platform")

        # If a service user is reported.
        if self.user is not None:
            # If the user is a name.
            if isinstance(self.user, str):
                # Require a nonblank user value.
                _require_nonblank(self.user, "SandboxSpec.user")
            # Otherwise require a nonnegative integer UID.
            elif type(self.user) is not int or self.user < 0:
                # Throw.
                raise ValueError("SandboxSpec.user must be a nonblank string, a nonnegative integer, or `None`.")

        # If a working directory is reported.
        if self.working_directory is not None:
            # Require an absolute guest path.
            _require_guest_path(self.working_directory, "SandboxSpec.working_directory")

        # Require exact Boolean policy flags.
        if type(self.privileged) is not bool or type(self.host_network) is not bool:
            # Throw.
            raise ValueError("SandboxSpec.privileged and SandboxSpec.host_network must be Booleans.")

        # Require an immutable tuple of neutral mount declarations.
        if not isinstance(self.mounts, tuple) or any(not isinstance(mount, MountSpec) for mount in self.mounts):
            # Throw.
            raise ValueError("SandboxSpec.mounts must be a tuple of MountSpec values.")


# Represent the neutral facts a runtime requires before a create.
@dataclass(frozen = True, slots = True)
class RuntimeRequirements:
    # Record the effective sandbox facts.
    spec: SandboxSpec

    # Record the image requirement the builder must satisfy.
    artifact: ArtifactRequirement

    def __post_init__(self) -> None:
        # Require one sandbox spec.
        if not isinstance(self.spec, SandboxSpec):
            # Throw.
            raise ValueError("RuntimeRequirements.spec must be a SandboxSpec value.")

        # Require one artifact requirement.
        if not isinstance(self.artifact, ArtifactRequirement):
            # Throw.
            raise ValueError("RuntimeRequirements.artifact must be an ArtifactRequirement value.")
