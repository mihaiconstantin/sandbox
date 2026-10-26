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
