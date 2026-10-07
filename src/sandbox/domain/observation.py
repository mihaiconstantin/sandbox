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
