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
