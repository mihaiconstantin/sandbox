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
