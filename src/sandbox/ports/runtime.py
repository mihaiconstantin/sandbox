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
    if artifact.transport is not requirement.transport:
        # Throw.
        raise ArtifactRejected(
            transport = artifact.transport.value,
            reference = artifact.reference,
            detail = "The artifact transport does not match the runtime requirement.",
        )

    # Require the archive bytes for a byte-carrying transport.
    if artifact.transport is not ArtifactTransport.LOCAL_IMAGE and (
        artifact.archive_path is None or not artifact.archive_path.is_file()
    ):
        # Throw.
        raise ArtifactRejected(
            transport = artifact.transport.value,
            reference = artifact.reference,
            detail = "The artifact archive is unavailable.",
        )

    # Return the verified artifact.
    return artifact


# Represent a typed, read-only runtime-owned preparation token.
@runtime_checkable
class RuntimePreparation(Protocol):
    # Read the neutral requirements the runtime exposes to the caller.
    @property
    def requirements(self) -> RuntimeRequirements: ...


# Represent the port that creates and controls sandboxes from a prepared artifact.
@runtime_checkable
class Runtime(Protocol):
    # Resolve read-only runtime state and expose neutral requirements.
    def prepare(self, plan: SandboxPlan, definition: RecipeDefinition) -> RuntimePreparation: ...

    # Plan the effective UID and eligible volume targets without mutation.
    def plan_initialization(self, preparation: RuntimePreparation, artifact: BuildArtifact) -> Initialization: ...

    # Create and start one box from a prepared artifact without building or pulling.
    def create(
        self,
        preparation: RuntimePreparation,
        artifact: BuildArtifact,
        initialization: Initialization | None = None,
        *,
        output: OutputSink = SILENT,
    ) -> BoxObservation: ...

    # Observe one managed box by name, or report absence.
    def inspect(self, name: str) -> BoxObservation | None: ...

    # List every managed box in name order.
    def list(self) -> tuple[BoxObservation, ...]: ...

    # Start an existing box and report whether this call changed its state.
    def start(self, name: str) -> bool: ...

    # Stop an existing box and report whether this call changed its state.
    def stop(self, name: str) -> bool: ...

    # Enter a live box and return the shell exit status.
    def enter(self, name: str, shell: str, login: bool) -> int: ...

    # Preview the resources removed with a box without mutating them.
    def plan_removal(self, name: str) -> RemovalPlan: ...

    # Remove a box and its owned runtime resources by name.
    def remove(self, name: str) -> None: ...

    # Ensure one declared shared volume exists and report whether this call created it.
    def ensure_volume(self, name: str) -> EnsuredVolume: ...
