# Imports.
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Import the shared invariant helper and fixed project root.
from sandbox.domain._invariants import _require_nonblank
from sandbox.domain.mount import Mount, Network
from sandbox.domain.paths import PROJECT_ROOT, Workspace


# Represent the observed lifecycle state of a box.
class BoxState(StrEnum):
    # The runtime proves that no managed box exists.
    MISSING = "missing"

    # The runtime created the instance but did not complete its creation.
    CREATED = "created"

    # The instance is running.
    RUNNING = "running"

    # The instance is starting or restarting.
    STARTING = "starting"

    # The instance is stopping or being removed.
    STOPPING = "stopping"

    # The instance is stopped.
    STOPPED = "stopped"

    # The instance is dead or failed.
    FAILED = "failed"

    # The runtime reported a state outside the neutral vocabulary.
    UNKNOWN = "unknown"

    # Report whether lifecycle policy treats the state as live.
    @property
    def is_live(self) -> bool:
        # Treat only running instances as live; starting is not live for this provider.
        return self is BoxState.RUNNING


# Represent the read-only origin record of a box.
@dataclass(frozen = True)
class Provenance:
    # Record the catalogue name when the runtime exposes it.
    catalogue: str | None

    # Record the recipe name when the runtime exposes it.
    recipe: str | None

    def __post_init__(self) -> None:
        # If a catalogue name is present.
        if self.catalogue is not None:
            # Require a nonblank catalogue name.
            _require_nonblank(self.catalogue, "Provenance.catalogue")

        # If a recipe name is present.
        if self.recipe is not None:
            # Require a nonblank recipe name.
            _require_nonblank(self.recipe, "Provenance.recipe")


# Represent an opaque runtime instance reference.
@dataclass(frozen = True)
class RuntimeRef:
    # Record the backend identifier.
    id: str

    # Record the backend display name.
    name: str

    def __post_init__(self) -> None:
        # Require both reference parts for display.
        _require_nonblank(self.id, "RuntimeRef.id")
        _require_nonblank(self.name, "RuntimeRef.name")


# Represent an observed box as the runtime reports it.
@dataclass(frozen = True)
class BoxObservation:
    # Guarantee the box identity.
    name: str

    # Guarantee the observed lifecycle state.
    state: BoxState

    # Guarantee the origin record for a managed box.
    provenance: Provenance

    # Report the adapter-native display label.
    status_text: str | None = None

    # Report the resolved image reference.
    image: str | None = None

    # Report the configured working directory.
    working_directory: str | None = None

    # Report the project bind at the expected target.
    workspace: Workspace | None = None

    # Report observed mounts, or `None` when unavailable.
    mounts: tuple[Mount, ...] | None = None

    # Report observed networks, or `None` when unavailable.
    networks: tuple[Network, ...] | None = None

    # Report the opaque backend reference.
    backend: RuntimeRef | None = None

    def __post_init__(self) -> None:
        # Require guaranteed observation fields.
        _require_nonblank(self.name, "BoxObservation.name")

        # Require an observed state because absence is `None` from inspection.
        if not isinstance(self.state, BoxState) or self.state is BoxState.MISSING:
            # Throw.
            raise ValueError("BoxObservation.state must be an observed BoxState other than `missing`.")

        # Require provenance for a managed box.
        if not isinstance(self.provenance, Provenance):
            # Throw.
            raise ValueError("BoxObservation.provenance must be a Provenance value.")

        # Require every reported display string to be a string, allowing observed empty values.
        for field_name, value in (
            ("BoxObservation.status_text", self.status_text),
            ("BoxObservation.image", self.image),
            ("BoxObservation.working_directory", self.working_directory),
        ):
            # If the value is reported with a non-string type.
            if value is not None and not isinstance(value, str):
                # Throw.
                raise ValueError(f"{field_name} must be a string or `None`.")

        # If a workspace is reported.
        if self.workspace is not None:
            # Require the fixed target for this box.
            if not isinstance(self.workspace, Workspace) or self.workspace.target != f"{PROJECT_ROOT}/{self.name}":
                # Throw.
                raise ValueError("BoxObservation.workspace must use the fixed target for the observed box.")

        # If mounts are reported.
        if self.mounts is not None:
            # Require an immutable tuple of mounts.
            if not isinstance(self.mounts, tuple) or any(not isinstance(mount, Mount) for mount in self.mounts):
                # Throw.
                raise ValueError("BoxObservation.mounts must be `None` or a tuple of Mount values.")

        # If networks are reported.
        if self.networks is not None:
            # Require an immutable tuple of networks.
            if not isinstance(self.networks, tuple) or any(not isinstance(network, Network) for network in self.networks):
                # Throw.
                raise ValueError("BoxObservation.networks must be `None` or a tuple of Network values.")

        # If a backend reference is reported.
        if self.backend is not None and not isinstance(self.backend, RuntimeRef):
            # Throw.
            raise ValueError("BoxObservation.backend must be `None` or a RuntimeRef.")


# Represent a read-only preview of the resources removed with a box.
@dataclass(frozen = True)
class RemovalPlan:
    # Record the box identity.
    box: str

    # Record the display references for planned containers.
    containers: tuple[RuntimeRef, ...]

    # Record the display references for planned networks.
    networks: tuple[RuntimeRef, ...]

    def __post_init__(self) -> None:
        # Require the box identity and immutable reference tuples.
        _require_nonblank(self.box, "RemovalPlan.box")

        # If the container references are not an immutable tuple.
        if not isinstance(self.containers, tuple) or any(not isinstance(reference, RuntimeRef) for reference in self.containers):
            # Throw.
            raise ValueError("RemovalPlan.containers must be a tuple of RuntimeRef values.")

        # If the network references are not an immutable tuple.
        if not isinstance(self.networks, tuple) or any(not isinstance(reference, RuntimeRef) for reference in self.networks):
            # Throw.
            raise ValueError("RemovalPlan.networks must be a tuple of RuntimeRef values.")


# Export the observation values.
__all__: list[str] = ["BoxObservation", "BoxState", "Provenance", "RemovalPlan", "RuntimeRef"]
