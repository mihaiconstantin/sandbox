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


# Represent a stateful fake builder that records artifact preparations.
class FakeBuilder:
    # Construct a builder with an optional build declaration and archive contents.
    def __init__(self, *, buildable: bool = True, archive_contents: bytes = b"fake archive") -> None:
        # Require exact configuration facts.
        if type(buildable) is not bool:
            # Throw.
            raise ValueError("buildable must be a Boolean.")
        if not isinstance(archive_contents, bytes):
            # Throw.
            raise ValueError("archive_contents must be bytes.")

        # Store the behavior configuration and the prepared image store.
        self.buildable: bool = buildable
        self.archive_contents: bytes = archive_contents
        self.images: set[str] = set()
        self.requests: list[PrepareRequest] = []
        self._faults: deque[SandboxError] = deque()
