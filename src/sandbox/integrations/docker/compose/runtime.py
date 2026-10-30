# Imports.
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Import domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    EnsuredVolume,
    Initialization,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRef,
    RuntimeRequirements,
    SandboxPlan,
    VolumeInfo,
)

# Import the typed public errors.
from sandbox.errors.base import CommandFailure
from sandbox.errors.boxes import BoxAmbiguous, BoxNotFound, BoxNotReady, BoxNotRunning
from sandbox.errors.capabilities import UnsupportedFeature
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.create import CreateFailed, CreatePostconditionFailed
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.removal import IncompleteRemoval, NetworkInUse, NothingToRemove
from sandbox.errors.terminal import InteractiveTerminalRequired
from sandbox.errors.ownership import OwnershipViolation
from sandbox.errors.volumes import (
    VolumeCreateFailed,
    VolumeInUse,
    VolumeNotFound,
    VolumeOwnershipError,
    VolumeReferencesUnavailable,
)

# Import the runtime port and output values.
from sandbox.ports.output import SILENT, OutputSink
from sandbox.ports.runtime import Runtime, RuntimePreparation, require_compatible_artifact

# Import the Docker integration helpers.
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.compose_cli import ComposeCli
from sandbox.integrations.docker.invocation import compose_environment, user_probe_arguments
from sandbox.integrations.docker.preflight import require_compose

# Import the Compose integration values.
from sandbox.integrations.docker.compose.labels import (
    COMPOSE_PROJECT_LABEL,
    MANAGED_LABEL,
    PROJECT_LABEL,
    box_filters,
    container_labels,
    is_box_role,
    is_managed_volume,
    is_owned_by,
    is_retained_container,
    managed_container_filters,
    managed_volume_filters,
    network_labels,
    project_filters,
    volume_create_labels,
    volume_labels,
)
from sandbox.integrations.docker.compose.observation import (
    box_observation,
    container_is_running,
    container_reference,
    network_reference,
    volume_info,
)
from sandbox.integrations.docker.compose.override import initialization_hooks, render_override
from sandbox.integrations.docker.compose.projection import Projection, project_configuration, recipe_pre_start
from sandbox.integrations.docker.compose.safety import (
    validate_image_healthcheck,
    validate_projection,
    validate_realized,
    validate_secret_files,
)

# Import volume-name validation.
from sandbox.validation.identifiers import validate_volume_name


# Report whether the standard streams are interactive terminals.
def _standard_streams_are_terminals() -> bool:
    # Require both the input and output streams to be terminals.
    return os.isatty(0) and os.isatty(1)


# Record one discovered managed container.
@dataclass(frozen = True, slots = True)
class _FoundContainer:
    # Record the engine identifier used by direct state operations.
    identifier: str

    # Record the mapped observation.
    observation: BoxObservation


# Record the verified resources planned for removal.
@dataclass(frozen = True, slots = True)
class _PlannedResources:
    # Record the project container references.
    containers: tuple[RuntimeRef, ...]

    # Record the project network references.
    networks: tuple[RuntimeRef, ...]

    # Record the project container identifiers.
    container_ids: frozenset[str]

    # Record the inspected project network payloads.
    network_payloads: tuple[Mapping[str, Any], ...]


# Record the runtime-owned preparation token with neutral requirements.
@dataclass(frozen = True, slots = True)
class ComposePreparation:
    # Expose the neutral requirements the caller may read.
    requirements: RuntimeRequirements

    # Record the issuing runtime.
    _owner: object = field(repr = False, compare = False)

    # Record the neutral plan.
    _plan: SandboxPlan = field(repr = False, compare = False)

    # Record the opaque recipe source.
    _definition: RecipeDefinition = field(repr = False, compare = False)

    # Record the Compose interpolation environment.
    _environment: Mapping[str, str] = field(repr = False, compare = False)

    # Record the rendered base override.
    _override: str = field(repr = False, compare = False)

    # Record the base resolved configuration.
    _configuration: Mapping[str, Any] = field(repr = False, compare = False)

    # Record the base neutral projection and verification facts.
    _base_projection: Projection = field(repr = False, compare = False)

    # Record the raw recipe pre-start hooks.
    _recipe_hooks: tuple[dict[str, Any], ...] = field(repr = False, compare = False)


# Represent the Docker/Compose implementation of the runtime port.
class ComposeRuntime(Runtime):
    # Construct the runtime around the Docker gateway and a TTY probe.
    def __init__(self, docker: DockerCli, *, interactive_terminal: Callable[[], bool] | None = None) -> None:
        # Record the gateway and the terminal capability probe.
        self._docker: DockerCli = docker
        self._compose: ComposeCli = ComposeCli(docker)
        self._interactive_terminal: Callable[[], bool] = interactive_terminal or _standard_streams_are_terminals

    # List every managed box in project order.
    def list(self) -> tuple[BoxObservation, ...]:
        # Query every managed container identifier.
        identifiers: tuple[str, ...] = self._docker.container_ids(managed_container_filters(), operation = "list")

        # Inspect every managed candidate.
        inspected: list[Mapping[str, Any]] = [self._docker.inspect_container(identifier, operation = "list") for identifier in identifiers]

        # Prepare candidates grouped by project.
        candidates: dict[str, list[Mapping[str, Any]]] = {}

        # For each inspected managed container.
        for payload in inspected:
            # Read the candidate labels.
            labels: Mapping[str, str] = container_labels(payload)

            # If the container lost the managed label after the server-side filter.
            if labels.get(MANAGED_LABEL) != "true":
                # Skip the container.
                continue

            # Skip a retained lifecycle hook or one-off probe.
            if is_retained_container(labels):
                # Continue to the next candidate.
                continue

            # Skip a container that does not carry the box role.
            if not is_box_role(labels):
                # Continue to the next candidate.
                continue

            # Read the project identity.
            project: str | None = labels.get(PROJECT_LABEL)

            # If the project name is missing or disagrees with the Compose project.
            if not project or labels.get(COMPOSE_PROJECT_LABEL) != project:
                # Continue to the next candidate.
                continue

            # Group the candidate by its project.
            candidates.setdefault(project, []).append(payload)

        # Prepare the observations.
        observations: list[BoxObservation] = []

        # For each project in name order.
        for project in sorted(candidates):
            # Read the project's candidate containers.
            contenders: list[Mapping[str, Any]] = candidates[project]

            # If more than one container claims the project.
            if len(contenders) > 1:
                # Report the ambiguity instead of a partial listing.
                raise BoxAmbiguous(project, len(contenders), backend = "docker")

            # Map the inspected container onto an observation.
            observations.append(box_observation(project, contenders[0]))

        # Return the observations in project order.
        return tuple(observations)
