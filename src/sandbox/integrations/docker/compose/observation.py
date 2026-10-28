# Imports.
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Import domain values.
from sandbox.domain import (
    PROJECT_ROOT,
    BoxObservation,
    BoxState,
    Mount,
    Network,
    Provenance,
    RuntimeRef,
    VolumeInfo,
    Workspace,
)

# Import the typed output error.
from sandbox.errors.engine import EngineOutputInvalid

# Import label accessors.
from sandbox.integrations.docker.compose.labels import (
    CATALOGUE_LABEL,
    RECIPE_LABEL,
    container_labels,
)

# Map the Docker status onto the neutral state vocabulary.
STATE_BY_STATUS: dict[str, BoxState] = {
    "created": BoxState.CREATED,
    "running": BoxState.RUNNING,
    "paused": BoxState.RUNNING,
    "restarting": BoxState.STARTING,
    "removing": BoxState.STOPPING,
    "exited": BoxState.STOPPED,
    "dead": BoxState.FAILED,
}


# Map one Docker status onto a neutral state.
def state_from_status(status: str | None) -> BoxState:
    # Preserve an unknown or absent status as the neutral unknown state.
    if status is None:
        # Report the unknown state.
        return BoxState.UNKNOWN

    # Return the mapped state or the unknown fallback.
    return STATE_BY_STATUS.get(status, BoxState.UNKNOWN)


# Report whether one container is running.
def container_is_running(payload: Mapping[str, Any]) -> bool:
    # Read the engine running flag with a false fallback.
    state: Any = payload.get("State") or {}
    if not isinstance(state, Mapping):
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")
    return bool(state.get("Running"))
