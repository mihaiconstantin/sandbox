"""Define one behavior scenario set for the neutral Builder and Runtime ports.

Subclasses supply a fresh adapter through the fixtures. No scenario inspects a protocol
signature or a private attribute; expectations come from the neutral value contracts,
ADR 0007, ADR 0008, and the rewrite specification.
"""

# Imports.
from collections.abc import Callable
from pathlib import Path

# Import pytest for fixtures and error assertions.
import pytest

# Import neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    Provenance,
    RecipeDefinition,
    RuntimeRequirements,
    SandboxPlan,
    SandboxSpec,
    VolumeDeclaration,
)

# Import the public capability and lifecycle errors used by the contract.
from sandbox.errors import BoxNotRunning
from sandbox.errors.capabilities import ArtifactRejected, CapabilityError

# Import the neutral port protocols.
from sandbox.ports.builder import Builder
from sandbox.ports.output import ProgressPhase
from sandbox.ports.runtime import Runtime, RuntimePreparation

# Import the recording sink.
from sandbox.testing.output import RecordingOutputSink

# Import neutral fixtures.
from neutral_fixtures import make_definition, make_plan, make_volume


# Build an artifact that satisfies the preparation's requirements.
def build_matching_artifact(preparation: RuntimePreparation, directory: Path) -> BuildArtifact:
    # Read the requirement from the preparation token.
    requirement: ArtifactRequirement = preparation.requirements.artifact

    # Create the operation-scoped archive when the transport carries bytes.
    archive: Path | None = None
    if requirement.transport is not ArtifactTransport.LOCAL_IMAGE:
        archive = directory / "contract-artifact.tar"
        archive.write_bytes(b"contract archive")

    # Return the typed artifact.
    return BuildArtifact(
        reference = requirement.reference,
        platform = requirement.platform,
        digest = None,
        transport = requirement.transport,
        archive_path = archive,
        created = False,
    )


# Build an artifact that deliberately disagrees with one requirement fact.
def build_mismatched_artifact(preparation: RuntimePreparation, directory: Path, *, reference: bool = False, transport: bool = False) -> BuildArtifact:
    # Read the requirement from the preparation token.
    requirement: ArtifactRequirement = preparation.requirements.artifact

    # Choose the alternate transport.
    effective_transport: ArtifactTransport = requirement.transport
    if transport:
        effective_transport = (
            ArtifactTransport.DOCKER_ARCHIVE
            if requirement.transport is ArtifactTransport.LOCAL_IMAGE
            else ArtifactTransport.LOCAL_IMAGE
        )

    # Create the archive for a byte-carrying transport.
    archive: Path | None = None
    if effective_transport is not ArtifactTransport.LOCAL_IMAGE:
        archive = directory / "mismatched-artifact.tar"
        archive.write_bytes(b"mismatched archive")

    # Return the artifact with the requested mismatch.
    return BuildArtifact(
        reference = f"{requirement.reference}-other" if reference else requirement.reference,
        platform = requirement.platform,
        digest = None,
        transport = effective_transport,
        archive_path = archive,
        created = False,
    )


# Define the shared builder scenarios.
class BuilderContract:
    # Supply a fresh builder for each test.
    @pytest.fixture
    def builder(self) -> Builder:
        # Require the concrete contract subclass to provide its adapter.
        raise NotImplementedError

    # Build the neutral plan used by the scenarios.
    @pytest.fixture
    def plan(self) -> SandboxPlan:
        # Return a volume-less plan.
        return make_plan()

    # Build the opaque recipe source used by the scenarios.
    @pytest.fixture
    def definition(self) -> RecipeDefinition:
        # Return a standard opaque definition.
        return make_definition()

    # Record the output emitted by the builder.
    @pytest.fixture
    def output(self) -> RecordingOutputSink:
        # Return a fresh recording sink.
        return RecordingOutputSink()

    # Declare the requirement the scenarios satisfy.
    @pytest.fixture
    def requirement(self) -> ArtifactRequirement:
        # Require a local image by default.
        return ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    # Report whether the first preparation is expected to create the image.
    @pytest.fixture
    def expects_initial_creation(self) -> bool:
        # Assume a fresh image store by default.
        return True

    # Report whether the selected service declares a build.
    @pytest.fixture
    def buildable(self) -> bool:
        # Assume the selected service declares a build.
        return True

    # Report whether the first preparation is expected to run a build.
    @pytest.fixture
    def expects_initial_build(self, buildable: bool) -> bool:
        # An image-only service is pulled rather than built.
        return buildable

    # Verify a preparation returns an artifact satisfying the requirement.
    def test_prepare_returns_an_artifact_satisfying_the_requirement(
        self,
        builder: Builder,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        output: RecordingOutputSink,
        expects_initial_creation: bool,
    ) -> None:
        # Prepare the image.
        artifact: BuildArtifact = builder.prepare(plan, definition, requirement, output = output)

        # Compare the neutral artifact facts with the requirement.
        assert isinstance(artifact, BuildArtifact)
        assert artifact.reference == requirement.reference
        assert artifact.transport is requirement.transport
        assert artifact.platform == requirement.platform
        assert artifact.created is expects_initial_creation

    # Verify a rebuild builds a buildable image but an image-only service is reused.
    def test_rebuild_builds_a_buildable_image_and_reuses_an_image_only_image(
        self,
        builder: Builder,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        output: RecordingOutputSink,
        expects_initial_creation: bool,
        buildable: bool,
    ) -> None:
        # Prepare the image twice, requesting a rebuild the second time.
        first: BuildArtifact = builder.prepare(plan, definition, requirement, output = output)
        phases_after_first: tuple[ProgressPhase, ...] = output.progress_phases
        second: BuildArtifact = builder.prepare(plan, definition, requirement, rebuild = True, output = output)

        # Require the first result to reflect the initial image store.
        assert first.created is expects_initial_creation
        assert second.reference == requirement.reference
        assert second.transport is requirement.transport

        # Require a buildable image to rebuild and an image-only service to reuse.
        assert second.created is buildable
        expected_build_events: int = phases_after_first.count(ProgressPhase.BUILD_IMAGE) + (1 if buildable else 0)
        assert output.progress_phases.count(ProgressPhase.BUILD_IMAGE) == expected_build_events

    # Verify the build phase is emitted only when an actual build ran.
    def test_build_image_is_emitted_only_for_an_actual_build(
        self,
        builder: Builder,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        output: RecordingOutputSink,
        expects_initial_creation: bool,
        expects_initial_build: bool,
        buildable: bool,
    ) -> None:
        # Prepare once, reuse once, and request an explicit rebuild.
        builder.prepare(plan, definition, requirement, output = output)
        phases_after_first: tuple[ProgressPhase, ...] = output.progress_phases
        builder.prepare(plan, definition, requirement, output = output)
        builder.prepare(plan, definition, requirement, rebuild = True, output = output)

        # Require the build phase exactly when the image was built, not pulled or reused.
        initial_build_events: int = 1 if (expects_initial_creation and expects_initial_build) else 0
        assert phases_after_first.count(ProgressPhase.BUILD_IMAGE) == initial_build_events

        # Only an explicit rebuild of a buildable image adds one further build.
        expected_build_events: int = initial_build_events + (1 if buildable else 0)
        assert output.progress_phases.count(ProgressPhase.BUILD_IMAGE) == expected_build_events

    # Verify an archive transport produces one operation-scoped archive.
    def test_archive_transport_produces_an_operation_scoped_archive(
        self,
        builder: Builder,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        output: RecordingOutputSink,
        tmp_path: Path,
    ) -> None:
        # Require a Docker archive.
        requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)

        # Prepare the archive inside the caller-owned staging directory.
        artifact: BuildArtifact = builder.prepare(plan, definition, requirement, staging_dir = tmp_path, output = output)

        # Require the archive to be a real file inside the staging directory.
        assert artifact.transport is ArtifactTransport.DOCKER_ARCHIVE
        assert artifact.archive_path is not None
        assert artifact.archive_path.is_relative_to(tmp_path)
        assert artifact.archive_path.is_file()

    # Verify an unsupported transport fails before any image preparation.
    def test_unsupported_transport_is_rejected_before_building(
        self,
        builder: Builder,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        output: RecordingOutputSink,
        expects_initial_creation: bool,
    ) -> None:
        # Require an unimplemented OCI archive for the adapter's effective reference.
        unsupported: ArtifactRequirement = ArtifactRequirement(
            reference = requirement.reference,
            platform = requirement.platform,
            transport = ArtifactTransport.OCI_ARCHIVE,
        )
        with pytest.raises(ArtifactRejected):
            builder.prepare(plan, definition, unsupported, output = output)

        # Require the rejection to happen before a build phase or image creation.
        assert ProgressPhase.BUILD_IMAGE not in output.progress_phases

        # A supported local image must still be prepared from the fresh image store.
        artifact: BuildArtifact = builder.prepare(plan, definition, requirement, output = output)
        assert artifact.created is expects_initial_creation


# Define the shared runtime scenarios.
class RuntimeContract:
    # Supply a fresh runtime for each test.
    @pytest.fixture
    def runtime(self) -> Runtime:
        # Require the concrete contract subclass to provide its adapter.
        raise NotImplementedError

    # Supply a second, independent runtime used to prove token ownership.
    @pytest.fixture
    def other_runtime(self) -> Runtime:
        # Require the concrete contract subclass to provide its adapter.
        raise NotImplementedError

    # Build the neutral plan used by the scenarios.
    @pytest.fixture
    def plan(self) -> SandboxPlan:
        # Return a volume-less plan.
        return make_plan()

    # Build a plan with one declared volume.
    @pytest.fixture
    def volume_plan(self) -> tuple[SandboxPlan, VolumeDeclaration]:
        # Build the plan and its declaration.
        declaration: VolumeDeclaration = make_volume()
        return make_plan(volumes = (declaration,)), declaration

    # Build the opaque recipe source used by the scenarios.
    @pytest.fixture
    def definition(self) -> RecipeDefinition:
        # Return a standard opaque definition.
        return make_definition()

    # Record the output emitted by the runtime.
    @pytest.fixture
    def output(self) -> RecordingOutputSink:
        # Return a fresh recording sink.
        return RecordingOutputSink()

    # Report the shell status the runtime must preserve.
    @pytest.fixture
    def enter_status(self) -> int:
        # Return a successful shell status.
        return 0

    # Build an independent runtime configured for one interactive shell status.
    @pytest.fixture
    def runtime_with_enter_status(self) -> Callable[[int], Runtime]:
        # Require the concrete contract subclass to provide its adapter.
        raise NotImplementedError

    # Build an artifact that matches the preparation's requirements.
    @pytest.fixture
    def artifact(self, preparation: RuntimePreparation, tmp_path: Path) -> BuildArtifact:
        # Return the matching artifact.
        return build_matching_artifact(preparation, tmp_path)

    # Prepare the default plan.
    @pytest.fixture
    def preparation(self, runtime: Runtime, plan: SandboxPlan, definition: RecipeDefinition) -> RuntimePreparation:
        # Return a read-only preparation.
        return runtime.prepare(plan, definition)

    # Create a box from the default plan.
    def create_box(self, runtime: Runtime, plan: SandboxPlan, definition: RecipeDefinition, output: RecordingOutputSink, directory: Path) -> BoxObservation:
        # Prepare, accept the artifact, plan initialization, and create.
        preparation: RuntimePreparation = runtime.prepare(plan, definition)
        artifact: BuildArtifact = build_matching_artifact(preparation, directory)
        initialization = runtime.plan_initialization(preparation, artifact)
        return runtime.create(preparation, artifact, initialization, output = output)

    # Verify preparation is read-only and exposes neutral requirements.
    def test_prepare_is_read_only_and_exposes_neutral_requirements(
        self,
        runtime: Runtime,
        plan: SandboxPlan,
        definition: RecipeDefinition,
    ) -> None:
        # Prepare the runtime state.
        preparation: RuntimePreparation = runtime.prepare(plan, definition)

        # Compare the neutral requirements.
        assert isinstance(preparation, RuntimePreparation)
        assert isinstance(preparation.requirements, RuntimeRequirements)
        assert isinstance(preparation.requirements.spec, SandboxSpec)
        assert preparation.requirements.spec.working_directory == plan.workspace.target
        assert preparation.requirements.artifact.reference

        # Require the preparation to leave the runtime unchanged.
        assert runtime.inspect(plan.project.name) is None
        assert runtime.list() == ()

    # Verify a mismatched artifact reference fails before mutation.
    def test_create_rejects_a_mismatched_reference_before_mutation(
        self,
        runtime: Runtime,
        plan: SandboxPlan,
        output: RecordingOutputSink,
        tmp_path: Path,
    ) -> None:
        # Prepare and build an artifact with the wrong reference.
        preparation: RuntimePreparation = runtime.prepare(plan, make_definition())
        artifact: BuildArtifact = build_mismatched_artifact(preparation, tmp_path, reference = True)

        # Require a typed capability failure and no box mutation.
        with pytest.raises(CapabilityError):
            runtime.create(preparation, artifact, output = output)
        assert runtime.inspect(plan.project.name) is None

    # Verify a mismatched artifact transport fails before mutation.
    def test_create_rejects_a_mismatched_transport_before_mutation(
        self,
        runtime: Runtime,
        plan: SandboxPlan,
        output: RecordingOutputSink,
        tmp_path: Path,
    ) -> None:
        # Prepare and build an artifact with another transport.
        preparation: RuntimePreparation = runtime.prepare(plan, make_definition())
        artifact: BuildArtifact = build_mismatched_artifact(preparation, tmp_path, transport = True)

        # Require a typed capability failure and no box mutation.
        with pytest.raises(CapabilityError):
            runtime.create(preparation, artifact, output = output)
        assert runtime.inspect(plan.project.name) is None

    # Verify a token from another runtime is rejected before mutation.
    def test_foreign_preparation_token_is_rejected_before_mutation(
        self,
        runtime: Runtime,
        other_runtime: Runtime,
        plan: SandboxPlan,
        tmp_path: Path,
    ) -> None:
        # Prepare with the other runtime.
        foreign: RuntimePreparation = other_runtime.prepare(plan, make_definition())
        artifact: BuildArtifact = build_matching_artifact(foreign, tmp_path)

        # Require a typed capability failure and no box mutation.
        with pytest.raises(CapabilityError):
            runtime.plan_initialization(foreign, artifact)
        assert runtime.inspect(plan.project.name) is None

    # Verify initialization planning resolves a numeric UID and declared targets.
    def test_plan_initialization_resolves_the_uid_and_declared_targets(
        self,
        runtime: Runtime,
        volume_plan: tuple[SandboxPlan, VolumeDeclaration],
        definition: RecipeDefinition,
        tmp_path: Path,
    ) -> None:
        # Prepare the volume-bearing plan and ensure its declared volume.
        plan, declaration = volume_plan
        preparation: RuntimePreparation = runtime.prepare(plan, definition)
        artifact: BuildArtifact = build_matching_artifact(preparation, tmp_path)
        ensured = runtime.ensure_volume(declaration.name)
        assert ensured.created is True

        # Plan the initialization.
        initialization = runtime.plan_initialization(preparation, artifact)

        # Require a numeric UID and only declared volume targets.
        assert isinstance(initialization.uid, int)
        assert initialization.uid >= 0
        assert set(initialization.targets) <= {candidate.target for candidate in plan.volumes}

        # Require the planning call to remain read-only.
        assert runtime.inspect(plan.project.name) is None

    # Verify creation returns one live box from a matching artifact.
    def test_create_from_a_matching_artifact_creates_one_box(
        self,
        runtime: Runtime,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        output: RecordingOutputSink,
        tmp_path: Path,
    ) -> None:
        # Create the box.
        observation: BoxObservation = self.create_box(runtime, plan, definition, output, tmp_path)

        # Compare the neutral post-create observation.
        assert observation.name == plan.project.name
        assert observation.state.is_live
        assert observation.provenance == Provenance(catalogue = definition.catalogue, recipe = definition.recipe)

        # Require inspection and listing to report the same box.
        assert runtime.inspect(plan.project.name) == observation
        assert runtime.list() == (observation,)

    # Verify lifecycle operations report their state changes and preserve shell status.
    def test_start_stop_and_enter_follow_the_lifecycle(
        self,
        runtime: Runtime,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        output: RecordingOutputSink,
        enter_status: int,
        tmp_path: Path,
    ) -> None:
        # Create the box.
        self.create_box(runtime, plan, definition, output, tmp_path)
        name: str = plan.project.name

        # Stop the live box and repeat the no-op transition.
        assert runtime.stop(name) is True
        assert runtime.stop(name) is False
        stopped: BoxObservation | None = runtime.inspect(name)
        assert stopped is not None
        assert stopped.state is BoxState.STOPPED

        # Refuse to enter a stopped box.
        with pytest.raises(BoxNotRunning):
            runtime.enter(name, "bash", False)

        # Start the stopped box and repeat the no-op transition.
        assert runtime.start(name) is True
        assert runtime.start(name) is False
        restarted: BoxObservation | None = runtime.inspect(name)
        assert restarted is not None
        assert restarted.state.is_live

        # Preserve the shell exit status.
        assert runtime.enter(name, "bash", False) == enter_status

    # Verify enter preserves success and positive statuses and normalizes non-positive ones.
    def test_enter_normalizes_nonpositive_shell_status(
        self,
        runtime_with_enter_status: Callable[[int], Runtime],
        plan: SandboxPlan,
        definition: RecipeDefinition,
        tmp_path: Path,
    ) -> None:
        # Cover success, a positive status, and two signal-style statuses.
        cases: tuple[tuple[int, int], ...] = ((0, 0), (125, 125), (-1, 1), (-15, 1))

        # Require each adapter to apply the documented status rule.
        for raw_status, expected_status in cases:
            # Create a fresh box for the status.
            runtime: Runtime = runtime_with_enter_status(raw_status)
            self.create_box(runtime, plan, definition, RecordingOutputSink(), tmp_path)

            # Compare the normalized shell status.
            assert runtime.enter(plan.project.name, "bash", False) == expected_status

    # Verify volume creation is idempotent and observable.
    def test_ensure_volume_reports_creation_once(
        self,
        runtime: Runtime,
        volume_plan: tuple[SandboxPlan, VolumeDeclaration],
    ) -> None:
        # Read the declared volume name.
        _, declaration = volume_plan

        # Ensure a declared volume and repeat the call.
        first = runtime.ensure_volume(declaration.name)
        second = runtime.ensure_volume(declaration.name)

        # Compare the creation reports.
        assert first.created is True
        assert second.created is False
        assert first.info.name == second.info.name == declaration.name

        # Require observation and listing to report the volume.
        assert runtime.inspect_volume(declaration.name) == second.info
        assert declaration.name in {info.name for info in runtime.list_volumes()}

    # Verify removal deletes the box but preserves shared volumes.
    def test_removal_deletes_the_box_and_keeps_shared_volumes(
        self,
        runtime: Runtime,
        volume_plan: tuple[SandboxPlan, VolumeDeclaration],
        definition: RecipeDefinition,
        output: RecordingOutputSink,
        tmp_path: Path,
    ) -> None:
        # Prepare the volume-bearing plan and ensure its volumes.
        plan, declaration = volume_plan
        preparation: RuntimePreparation = runtime.prepare(plan, definition)
        artifact: BuildArtifact = build_matching_artifact(preparation, tmp_path)
        runtime.ensure_volume(declaration.name)
        initialization = runtime.plan_initialization(preparation, artifact)
        runtime.create(preparation, artifact, initialization, output = output)

        # Preview and remove the box.
        removal = runtime.plan_removal(plan.project.name)
        assert removal.box == plan.project.name
        runtime.remove(plan.project.name)
        assert runtime.inspect(plan.project.name) is None

        # Require the volume to survive the box removal.
        assert runtime.inspect_volume(declaration.name) is not None


# Allow the focused module to be imported by the adapter contract tests.
__all__ = ["BuilderContract", "RuntimeContract", "build_matching_artifact", "build_mismatched_artifact"]
