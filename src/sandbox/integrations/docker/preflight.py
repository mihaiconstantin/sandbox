# Imports.
from __future__ import annotations

import re

# Import the public prerequisite failure.
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Import the gateways used by the preflight probes.
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.compose_cli import ComposeCli
from sandbox.integrations.docker.invocation import buildx_version_arguments

# Declare the supported host-tool floors.
COMPOSE_MINIMUM: str = "5.6.0"
BUILDX_MINIMUM: str = "0.17.0"

# Match the first semantic version in a tool banner.
_VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")


# Return the numeric semantic version tuple found in one tool banner.
def parse_version(output: str) -> tuple[int, int, int] | None:
    # Find the first version anywhere in the banner.
    match: re.Match[str] | None = _VERSION_PATTERN.search(output)

    # Report an unparseable version as absent.
    if match is None:
        # Return no version.
        return None

    # Read the captured numeric components.
    major, minor, patch = match.groups()

    # Normalize a missing patch component.
    return (int(major), int(minor), int(patch or 0))


# Compare two numeric version tuples without padding surprises.
def meets_minimum(found: tuple[int, int, int], minimum: str) -> bool:
    # Parse the required floor.
    required: tuple[int, int, int] | None = parse_version(minimum)

    # A malformed internal floor is a programming error.
    if required is None:
        # Throw.
        raise ValueError(f"Invalid minimum version `{minimum}`.")

    # Compare the normalized numeric components.
    return found >= required


# Require a usable Compose version at or above the supported floor.
def require_compose(compose: ComposeCli, *, operation: str = "preflight") -> None:
    # Read the installed Compose version without treating a failed probe as an engine failure.
    result: CommandResult = compose.version_result()

    # If the version command failed.
    if result.returncode != 0:
        # Classify a missing plugin separately from an unusable installation.
        kind: PrerequisiteKind = PrerequisiteKind.MISSING if _mentions_missing_plugin(result) else PrerequisiteKind.UNUSABLE

        # Throw the actionable prerequisite failure.
        raise PrerequisiteError(
            "docker compose",
            kind,
            requirement = f">={COMPOSE_MINIMUM}",
            operation = operation,
            diagnostic = result.diagnostic,
            hint = "Install Docker Compose v5.6.0 or newer.",
        )

    # Parse the short version banner.
    found: tuple[int, int, int] | None = parse_version(_tool_output(result))

    # If the version is absent, treat the tool as unusable.
    if found is None:
        # Throw.
        raise PrerequisiteError(
            "docker compose",
            PrerequisiteKind.UNUSABLE,
            requirement = f">={COMPOSE_MINIMUM}",
            operation = operation,
            diagnostic = result.diagnostic,
            hint = "Install Docker Compose v5.6.0 or newer.",
        )

    # If the installed version is below the supported floor.
    if not meets_minimum(found, COMPOSE_MINIMUM):
        # Throw the unsupported-version failure.
        raise PrerequisiteError(
            "docker compose",
            PrerequisiteKind.VERSION,
            requirement = f">={COMPOSE_MINIMUM}",
            found = _version_text(found),
            operation = operation,
            diagnostic = result.diagnostic,
            hint = "Upgrade Docker Compose to v5.6.0 or newer.",
        )


# Require a usable Buildx version at or above the supported floor when a build runs.
def require_buildx(docker: DockerCli, *, operation: str = "build") -> None:
    # Probe the Buildx plugin version.
    arguments: list[str] = buildx_version_arguments()
    result: CommandResult = docker.run(arguments, operation = operation)

    # If the version command failed.
    if result.returncode != 0:
        # Classify a missing plugin separately from an unusable installation.
        kind: PrerequisiteKind = PrerequisiteKind.MISSING if _mentions_missing_plugin(result) else PrerequisiteKind.UNUSABLE

        # Throw the actionable prerequisite failure.
        raise PrerequisiteError(
            "buildx",
            kind,
            requirement = f">={BUILDX_MINIMUM}",
            operation = operation,
            diagnostic = result.diagnostic,
            hint = "Install the Docker Buildx plugin v0.17.0 or newer.",
        )

    # Parse the version from the plugin banner.
    found: tuple[int, int, int] | None = parse_version(_tool_output(result))

    # If the version is absent, treat the plugin as unusable.


# Report whether a failed plugin probe means the plugin is absent.
def _mentions_missing_plugin(result: CommandResult) -> bool:
    # Inspect both streams because Docker prints plugin discovery errors to either.
    detail: str = f"{result.stdout.decode('utf-8', errors = 'replace')}\n{result.stderr.decode('utf-8', errors = 'replace')}".lower()

    # Recognize Docker's plugin discovery messages.
    return any(
        marker in detail
        for marker in (
            "is not a docker command",
            "unknown command",
            "not a docker command",
            "no such plugin",
            "plugin not found",
            "not found",
        )
    )


# Read the combined output of one version probe.
def _tool_output(result: CommandResult) -> str:
    # Join both streams so a warning on stderr cannot hide the version banner.
    return f"{result.stdout.decode('utf-8', errors = 'replace')}\n{result.stderr.decode('utf-8', errors = 'replace')}"


# Format one numeric version tuple for structured facts.
def _version_text(version: tuple[int, int, int]) -> str:
    # Join the numeric components.
    return ".".join(str(component) for component in version)
