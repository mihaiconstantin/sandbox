# Imports.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

# Import the neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BuildArtifact,
    RecipeDefinition,
    SandboxPlan,
)

# Import the neutral errors.
from sandbox.errors import SandboxError
from sandbox.errors.capabilities import ArtifactRejected

# Import the output port values.
from sandbox.ports.output import SILENT, OutputSink, ProgressPhase


# Represent one recorded artifact preparation request.
@dataclass(frozen = True, slots = True)
class PrepareRequest:
    # Record the neutral plan.
    plan: SandboxPlan

    # Record the opaque recipe source.
    definition: RecipeDefinition

    # Record the runtime's artifact requirement.
    requirement: ArtifactRequirement

    # Report whether a rebuild was requested.
    rebuild: bool

    # Record the caller-owned staging directory.
    staging_dir: Path | None
