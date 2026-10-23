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


# Build the `docker` compose argument prefix pinned to the catalogue root and ordered files.
def compose_arguments(definition: RecipeDefinition, compose_files: Sequence[Path]) -> list[str]:
    # Start with the Compose command and a plain, non-interactive progress mode.
    arguments: list[str] = ["docker", "compose", "--progress", "plain", "--project-directory", str(definition.catalogue_root)]

    # Append every `docker` compose file in parent-first order.
    for path in compose_files:
        # Add the ordered file.
        arguments.extend(["-f", str(path)])

    # Return the complete argument prefix.
    return arguments


# Build the `docker` compose configuration command.
def compose_config_arguments(definition: RecipeDefinition, compose_files: Sequence[Path]) -> list[str]:
    # Start with the shared compose invocation prefix.
    arguments: list[str] = compose_arguments(definition, compose_files)

    # Request the fully resolved configuration as JSON.
    arguments.extend(["config", "--format", "json"])

    # Return the complete command.
    return arguments


# Build the `docker` compose build command for one selected service.
def compose_build_arguments(definition: RecipeDefinition, compose_files: Sequence[Path], service: str) -> list[str]:
    # Start with the shared compose invocation prefix.
    arguments: list[str] = compose_arguments(definition, compose_files)

    # Build the selected service and every dependency without changing image tags or cache policy.
    arguments.extend(["build", "--with-dependencies", service])

    # Return the complete command.
    return arguments


# Build the version command used by the Compose prerequisite preflight.
def compose_version_arguments() -> list[str]:
    # Return the short version probe without a project.
    return ["docker", "compose", "version", "--short"]
