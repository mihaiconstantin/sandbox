# Imports.
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

# Import the opaque recipe source.
from sandbox.domain import RecipeDefinition


# Prepare the environment used for `docker` compose interpolation and project identity.
def compose_environment(
    project: str,
    project_directory: Path,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    # Copy the caller's environment without mutating process state.
    environment: dict[str, str] = dict(os.environ if base is None else base)

    # Export the project identity and directory for `docker` compose interpolation.
    environment["SB_PROJECT_NAME"] = project
    environment["SB_PROJECT_DIRECTORY"] = str(project_directory)

    # Select the Compose project name used by every current resource label.
    environment["COMPOSE_PROJECT_NAME"] = project

    # Disable disruptive Docker CLI hints for every child.
    environment["DOCKER_CLI_HINTS"] = "false"

    # Return the prepared environment.
    return environment
