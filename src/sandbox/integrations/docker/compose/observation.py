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


# Derive the project workspace from the reported mounts.
def _workspace(name: str, mounts: tuple[Mount, ...] | None) -> Workspace | None:
    # If mounts are unavailable.
    if mounts is None:
        # Report the workspace as unavailable.
        return None

    # Compute the fixed project target.
    target: str = f"{PROJECT_ROOT}/{name}"

    # For each reported mount.
    for mount in mounts:
        # If the mount is the project bind at the fixed target.
        if mount.kind == "bind" and mount.target == target:
            # Return the live project workspace.
            return Workspace(host_directory = Path(mount.source), target = target)

    # Report that no project bind was observed.
    return None


# Map the reported networks onto neutral values.
def _networks(payload: Mapping[str, Any]) -> tuple[Network, ...] | None:
    # If the payload does not report network settings.
    if "NetworkSettings" not in payload or payload.get("NetworkSettings") is None:
        # Report networks as unavailable.
        return None

    # Require the network settings mapping.
    settings: Any = payload.get("NetworkSettings")
    if not isinstance(settings, Mapping):
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")

    # Read the attached network mapping.
    reported: Any = settings.get("Networks") or {}
    if not isinstance(reported, Mapping):
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")

    # Prepare the mapped networks.
    networks: list[Network] = []

    # For each attached network.
    for name, details in reported.items():
        # Require a nonblank name and mapping details.
        if not isinstance(name, str) or not name or not isinstance(details, Mapping):
            # Throw for malformed engine data.
            raise EngineOutputInvalid("docker", "inspect", "")

        # Read the assigned address without fabricating one.
        address: Any = details.get("IPAddress") or ""

        # Record the network name and assigned address.
        networks.append(Network(name = name, ip_address = address if isinstance(address, str) else ""))

    # Return the reported networks, including an observed empty tuple.
    return tuple(networks)
