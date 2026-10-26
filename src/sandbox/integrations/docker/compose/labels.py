# Imports.
from collections.abc import Mapping
from typing import Any, cast

# Record the ownership label that marks a sandbox-managed resource.
MANAGED_LABEL: str = "sb.managed"

# Record the project identity label written by sandbox.
PROJECT_LABEL: str = "sb.project"

# Record the resource kind label written by sandbox.
RESOURCE_LABEL: str = "sb.resource"

# Record the box role label written by sandbox.
ROLE_LABEL: str = "sb.role"

# Record the shared-volume scope label written by sandbox.
SCOPE_LABEL: str = "sb.scope"

# Record the catalogue provenance label written by sandbox.
CATALOGUE_LABEL: str = "sb.catalogue"

# Record the recipe provenance label written by sandbox.
RECIPE_LABEL: str = "sb.recipe"

# Record the Compose project label.
COMPOSE_PROJECT_LABEL: str = "com.docker.compose.project"

# Record the Compose one-off label.
COMPOSE_ONEOFF_LABEL: str = "com.docker.compose.oneoff"

# Record the Compose lifecycle hook label.
COMPOSE_HOOK_LABEL: str = "com.docker.compose.hook"


# Return the exact managed-box discovery filters for one project.
def box_filters(name: str) -> dict[str, str]:
    # Return the five server-side filters in their current order.
    return {
        MANAGED_LABEL: "true",
        PROJECT_LABEL: name,
        COMPOSE_PROJECT_LABEL: name,
        ROLE_LABEL: "box",
        COMPOSE_ONEOFF_LABEL: "False",
    }


# Return the broad managed-container listing filters.
def managed_container_filters() -> dict[str, str]:
    # Return the ownership filter used by `list`.
    return {MANAGED_LABEL: "true"}


# Return the project-scoped removal filters.
def project_filters(name: str) -> dict[str, str]:
    # Return the Compose project label shared by removal resources.
    return {COMPOSE_PROJECT_LABEL: name}


# Return the managed-volume listing filters.
def managed_volume_filters() -> dict[str, str]:
    # Return the ownership filter used by volume listing.
    return {MANAGED_LABEL: "true"}


# Return the exact labels written when a shared volume is created.
def volume_create_labels() -> dict[str, str]:
    # Return the ownership, resource, and scope labels in creation order.
    return {
        MANAGED_LABEL: "true",
        RESOURCE_LABEL: "volume",
        SCOPE_LABEL: "shared",
    }


# Read the labels from one inspected container.
def container_labels(payload: Mapping[str, Any]) -> Mapping[str, str]:
    # Read the configuration mapping with an empty fallback.
    config: Any = payload.get("Config") or {}

    # If the configuration is not a mapping, report no labels.
    if not isinstance(config, Mapping):
        # Return an empty mapping.
        return {}

    # Read the labels with an empty fallback.
    labels: Any = config.get("Labels") or {}

    # If the labels are not a mapping, report no labels.
    if not isinstance(labels, Mapping):
        # Return an empty mapping.
        return {}

    # Return the reported labels.
    return cast(Mapping[str, str], labels)


# Read the labels from one inspected network.
def network_labels(payload: Mapping[str, Any]) -> Mapping[str, str]:
    # Read the labels with an empty fallback.
    labels: Any = payload.get("Labels") or {}

    # If the labels are not a mapping, report no labels.
    if not isinstance(labels, Mapping):
        # Return an empty mapping.
        return {}

    # Return the reported labels.
    return cast(Mapping[str, str], labels)


# Read the labels from one inspected volume.
def volume_labels(payload: Mapping[str, Any]) -> Mapping[str, str]:
    # Read the labels with an empty fallback.
    labels: Any = payload.get("Labels") or {}

    # If the labels are not a mapping, report no labels.
    if not isinstance(labels, Mapping):
        # Return an empty mapping.
        return {}

    # Return the reported labels.
    return cast(Mapping[str, str], labels)


# Report whether one container is a retained hook or one-off probe.
def is_retained_container(labels: Mapping[str, str]) -> bool:
    # Treat any hook label or one-off probe as a retained lifecycle resource.
    return bool(labels.get(COMPOSE_HOOK_LABEL)) or labels.get(COMPOSE_ONEOFF_LABEL) == "True"


# Report whether one container is a box-role candidate.
def is_box_role(labels: Mapping[str, str]) -> bool:
    # Require the current box role label.
    return labels.get(ROLE_LABEL) == "box"
