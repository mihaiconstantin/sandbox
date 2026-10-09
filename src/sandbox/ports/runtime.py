# Imports.
from __future__ import annotations

from typing import Protocol, runtime_checkable

# Import the neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BuildArtifact,
    EnsuredVolume,
    Initialization,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRequirements,
    SandboxPlan,
    VolumeInfo,
)

# Import the typed artifact rejection.
from sandbox.errors.capabilities import ArtifactRejected

# Import the neutral output sink and its silent default.
from sandbox.ports.output import SILENT, OutputSink


# Require an artifact to satisfy the runtime's neutral requirement before mutation.
def require_compatible_artifact(requirement: ArtifactRequirement, artifact: BuildArtifact) -> BuildArtifact:
    # Require the typed artifact value.
    if not isinstance(artifact, BuildArtifact):
        # Throw a programming error for a broken builder implementation.
        raise TypeError("builder.prepare must return a BuildArtifact.")

    # Require the canonical reference.
    if artifact.reference != requirement.reference:
        # Throw.
        raise ArtifactRejected(
            transport = artifact.transport.value,
            reference = artifact.reference,
            detail = "The artifact reference does not match the runtime requirement.",
        )

    # Require the constrained platform when the runtime declares one.
    if requirement.platform is not None and artifact.platform != requirement.platform:
        # Throw.
        raise ArtifactRejected(
            transport = artifact.transport.value,
            reference = artifact.reference,
            expected_platform = requirement.platform,
            actual_platform = artifact.platform,
            detail = "The artifact platform does not match the runtime requirement.",
        )

    # Require the accepted transport.
