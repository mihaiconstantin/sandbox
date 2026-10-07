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
