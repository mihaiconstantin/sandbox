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


# Map one inspected volume onto a neutral volume observation.
def volume_info(metadata: Mapping[str, Any], references: tuple[RuntimeRef, ...]) -> VolumeInfo:
    # Read and validate the physical name.
    name: str = _required_string(metadata, "Name")

    # Read the optional display fields.
    driver: Any = metadata.get("Driver")
    mountpoint: Any = metadata.get("Mountpoint")

    # Return the observed volume.
    return VolumeInfo(
        name = name,
        driver = driver if isinstance(driver, str) else None,
        mountpoint = mountpoint if isinstance(mountpoint, str) else None,
        in_use_by = references,
    )


# Build the display reference for one inspected container.
def container_reference(payload: Mapping[str, Any]) -> RuntimeRef:
    # Return the container identifier and normalized display name.
    return RuntimeRef(id = _required_string(payload, "Id"), name = _required_string(payload, "Name").removeprefix("/"))


# Build the display reference for one inspected network.
def network_reference(payload: Mapping[str, Any]) -> RuntimeRef:
    # Return the network identifier and display name.
    return RuntimeRef(id = _required_string(payload, "Id"), name = _required_string(payload, "Name"))


# Report whether one container is running.
def container_is_running(payload: Mapping[str, Any]) -> bool:
    # Read the engine running flag with a false fallback.
    state: Any = payload.get("State") or {}
    if not isinstance(state, Mapping):
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")
    return bool(state.get("Running"))


# Map the reported mounts onto neutral values.
def _mounts(payload: Mapping[str, Any]) -> tuple[Mount, ...] | None:
    # If the payload does not report mounts.
    if "Mounts" not in payload or payload.get("Mounts") is None:
        # Report mounts as unavailable.
        return None

    # Require an array of mounts.
    reported: Any = payload.get("Mounts")
    if not isinstance(reported, list):
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")

    # Prepare the mapped mounts.
    mounts: list[Mount] = []

    # For each reported mount.


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


# Report whether one inspected resource has both nonblank reference parts.
def _has_reference(payload: Mapping[str, Any]) -> bool:
    # Require both nonblank reference parts.
    identifier: Any = payload.get("Id")
    name: Any = payload.get("Name")
    return isinstance(identifier, str) and bool(identifier) and isinstance(name, str) and bool(name)


# Read one required nonblank string field from an inspected payload.
def _required_string(payload: Mapping[str, Any], field: str) -> str:
    # Read the field without coercing it.
    value: Any = payload.get(field)

    # If the field is not a nonblank string.
    if not isinstance(value, str) or not value:
        # Throw for malformed engine data.
        raise EngineOutputInvalid("docker", "inspect", "")

    # Return the validated value.
    return value
