# Imports.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace

# Import the neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    EnsuredVolume,
    Initialization,
    Mount,
    MountSpec,
    Provenance,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRef,
    RuntimeRequirements,
    SandboxPlan,
    SandboxSpec,
    VolumeInfo,
    secret_target,
)

# Import the neutral errors.
from sandbox.errors import (
    BoxNotFound,
    BoxNotReady,
    BoxNotRunning,
    NothingToRemove,
    SandboxError,
    VolumeInUse,
    VolumeNotFound,
)
from sandbox.errors.capabilities import UnsupportedFeature

# Import the runtime preparation protocol and output port values.
from sandbox.ports.output import SILENT, OutputChannel, OutputSink
from sandbox.ports.runtime import RuntimePreparation, require_compatible_artifact


# Represent one recorded preparation request.
@dataclass(frozen = True, slots = True)
class RuntimePrepareRequest:
    # Record the neutral plan.
    plan: SandboxPlan

    # Record the opaque recipe source.
    definition: RecipeDefinition


# Represent one recorded interactive enter request.
@dataclass(frozen = True, slots = True)
class EnterRequest:
    # Record the box identity.
    name: str

    # Record the requested shell.
    shell: str

    # Report whether a login shell was requested.
    login: bool
