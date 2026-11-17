# Imports.
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

# Import the opaque recipe source.
from sandbox.domain import RecipeDefinition


# Prepare one Docker child environment without mutating process state.
def docker_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    # Copy the caller's environment without mutating process state.
    environment: dict[str, str] = dict(os.environ if base is None else base)

    # Disable the Docker CLI hints printed after interactive commands.
    environment["DOCKER_CLI_HINTS"] = "false"

    # Return the prepared environment.
    return environment


# Prepare the environment used for `docker` compose interpolation and project identity.
def compose_environment(
    project: str,
    project_directory: Path,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    # Start from the shared Docker child environment.
    environment: dict[str, str] = docker_environment(base)

    # Export the project identity and directory for `docker` compose interpolation.
    environment["SB_PROJECT_NAME"] = project
    environment["SB_PROJECT_DIRECTORY"] = str(project_directory)

    # Select the Compose project name used by every current resource label.
    environment["COMPOSE_PROJECT_NAME"] = project

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


# Build the `docker` compose start command for one prepared service.
def compose_up_arguments(definition: RecipeDefinition, compose_files: Sequence[Path], service: str) -> list[str]:
    # Start with the shared compose invocation prefix.
    arguments: list[str] = compose_arguments(definition, compose_files)

    # Start the service without an implicit build or pull.
    arguments.extend(["up", "-d", "--no-build", "--pull", "never"])

    # Select the effective service last.
    arguments.append(service)

    # Return the complete command.
    return arguments


# Build the identity probe command for the prepared image without pulling.
def user_probe_arguments(image: str, user: str | int | None, platform: str | None) -> list[str]:
    # Run only the standard identity utility in the prepared image.
    arguments: list[str] = ["docker", "run", "--rm", "--no-healthcheck", "--pull=never"]

    # Select the same image platform that Compose used for the build.
    if platform:
        # Retain Docker's platform selection.
        arguments.extend(["--platform", platform])

    # Apply an explicit Compose user; otherwise Docker uses the image's USER.
    if user not in (None, ""):
        # Preserve the configured user or numeric UID.
        arguments.extend(["--user", str(user)])

    # Query the effective numeric UID without starting application code.
    arguments.extend(["--entrypoint", "/usr/bin/id", image, "-u"])

    # Return the complete probe command.
    return arguments


# Build the version command used by the Compose prerequisite preflight.
def compose_version_arguments() -> list[str]:
    # Return the short version probe without a project.
    return ["docker", "compose", "version", "--short"]


# Build the version command used by the Buildx prerequisite preflight.
def buildx_version_arguments() -> list[str]:
    # Return the Buildx plugin version probe.
    return ["docker", "buildx", "version"]


# Define the public API of the Compose invocation helpers.
__all__: list[str] = [
    "buildx_version_arguments",
    "compose_arguments",
    "compose_build_arguments",
    "compose_config_arguments",
    "compose_environment",
    "compose_up_arguments",
    "compose_version_arguments",
    "docker_environment",
    "user_probe_arguments",
]
