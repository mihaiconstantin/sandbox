"""Verify the shipped neutral fakes support state, artifact, and output assertions."""

# Imports.
import dataclasses
from pathlib import Path

# Import pytest for assertions.
import pytest

# Import neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxState,
    BuildArtifact,
    RuntimeRequirements,
)

# Import errors used by the fakes.
from sandbox.errors import BoxNotReady, VolumeInUse
from sandbox.errors.capabilities import ArtifactRejected

# Import the output values.
from sandbox.ports import OutputChannel, ProgressPhase

# Import the fakes.
from sandbox.testing.builder import FakeBuilder, PrepareRequest
from sandbox.testing.output import RecordedOutput, RecordingOutputSink
from sandbox.testing.runtime import FakeRuntime, RuntimePrepareRequest

# Import the neutral fixtures.
from neutral_fixtures import make_definition, make_initialization, make_plan, make_spec, make_volume


# Prepare, create, and return the effective runtime facts for a fake scenario.
def create_box(runtime: FakeRuntime, plan, definition, output: RecordingOutputSink | None = None):
    # Prepare the runtime state.
    preparation = runtime.prepare(plan, definition)

    # Build a matching local-image artifact.
    requirement: ArtifactRequirement = preparation.requirements.artifact
    artifact: BuildArtifact = BuildArtifact(
        reference = requirement.reference,
        platform = requirement.platform,
        digest = None,
        transport = requirement.transport,
        archive_path = None,
        created = False,
    )

    # Ensure the declared volumes first.
    for declaration in plan.volumes:
        runtime.ensure_volume(declaration.name)

    # Plan and perform the create.
    initialization = runtime.plan_initialization(preparation, artifact)
    return runtime.create(preparation, artifact, initialization, output = output or RecordingOutputSink())


# Verify the fake runtime derives neutral requirements when none are configured.
def test_fake_runtime_derives_neutral_requirements() -> None:
    # Prepare a volume-bearing plan.
    declaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    runtime: FakeRuntime = FakeRuntime()
    preparation = runtime.prepare(plan, make_definition())

    # Compare the derived spec and artifact requirement.
    spec = preparation.requirements.spec
    assert spec.image == "sandbox/demo:latest"
    assert spec.working_directory == plan.workspace.target
    assert spec.privileged is False
    assert spec.host_network is False
    assert {mount.target for mount in spec.mounts} == {plan.workspace.target, declaration.target}
    assert preparation.requirements.artifact == ArtifactRequirement(
        reference = "sandbox/demo:latest",
        platform = None,
        transport = ArtifactTransport.LOCAL_IMAGE,
    )

    # Require the recorded request.
    assert runtime.prepare_requests == [RuntimePrepareRequest(plan = plan, definition = make_definition())]


# Verify an explicitly configured requirement is preserved for artifact checks.
def test_fake_runtime_preserves_configured_requirements_and_rejects_mismatches(tmp_path: Path) -> None:
    # Configure an archive-transport runtime.
    plan = make_plan()
    requirement = ArtifactRequirement(reference = "sandbox/archive:latest", platform = "linux/arm64", transport = ArtifactTransport.DOCKER_ARCHIVE)
    requirements = RuntimeRequirements(spec = make_spec(plan), artifact = requirement)
    runtime: FakeRuntime = FakeRuntime(requirements = requirements)
    preparation = runtime.prepare(plan, make_definition())
    assert preparation.requirements is requirements

    # Reject a platform mismatch before mutation.
    mismatched: BuildArtifact = BuildArtifact(
        reference = requirement.reference,
        platform = "linux/amd64",
        digest = None,
        transport = ArtifactTransport.DOCKER_ARCHIVE,
        archive_path = tmp_path / "artifact.tar",
        created = False,
    )
    (tmp_path / "artifact.tar").write_bytes(b"archive")
    with pytest.raises(ArtifactRejected):
        runtime.create(preparation, mismatched)
    assert runtime.inspect(plan.project.name) is None

    # Accept a matching archive artifact.
    matching: BuildArtifact = BuildArtifact(
        reference = requirement.reference,
        platform = requirement.platform,
        digest = "sha256:contract",
        transport = ArtifactTransport.DOCKER_ARCHIVE,
        archive_path = tmp_path / "artifact.tar",
        created = False,
    )
    observation = runtime.create(preparation, matching)
    assert observation.name == plan.project.name
    assert observation.image == requirement.reference


# Verify create streams configured child output and never invents progress phases.
def test_fake_runtime_streams_configured_create_output() -> None:
    # Configure two raw chunks on both channels.
    plan = make_plan()
    sink: RecordingOutputSink = RecordingOutputSink()
    runtime: FakeRuntime = FakeRuntime(
        create_output = ((OutputChannel.STDOUT, b"step one\n"), (OutputChannel.STDERR, b"warning\n"), (OutputChannel.STDOUT, b"\xe2\x82\xac")),
    )

    # Create the box.
    create_box(runtime, plan, make_definition(), sink)

    # Require the exact ordered chunks and no progress from the adapter.
    assert sink.output_events == (
        RecordedOutput(channel = OutputChannel.STDOUT, data = b"step one\n"),
        RecordedOutput(channel = OutputChannel.STDERR, data = b"warning\n"),
        RecordedOutput(channel = OutputChannel.STDOUT, data = b"\xe2\x82\xac"),
    )
    assert sink.output_bytes(OutputChannel.STDOUT) == b"step one\n\xe2\x82\xac"
    assert sink.output_bytes(OutputChannel.STDERR) == b"warning\n"
    assert sink.progress_events == ()


# Verify lifecycle state and refusal rules.
def test_fake_runtime_enforces_lifecycle_state() -> None:
    # Create a running box.
    plan = make_plan()
    runtime: FakeRuntime = FakeRuntime()
    observation = create_box(runtime, plan, make_definition())
    assert observation.state is BoxState.RUNNING

    # Refuse a partially created box.
    runtime.add_box(dataclasses.replace(observation, state = BoxState.CREATED))
    with pytest.raises(BoxNotReady):
        runtime.start(plan.project.name)
    runtime.add_box(observation)

    # Stop once, then start once.
    assert runtime.stop(plan.project.name) is True
    assert runtime.stop(plan.project.name) is False
    stopped = runtime.inspect(plan.project.name)
    assert stopped is not None
    assert stopped.state is BoxState.STOPPED
    assert runtime.start(plan.project.name) is True


# Verify volume ownership references block removal until the box is removed.
def test_fake_runtime_tracks_volume_references() -> None:
    # Create a box that uses the declared volume.
    declaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    runtime: FakeRuntime = FakeRuntime()
    create_box(runtime, plan, make_definition())

    # Require the volume to report its holder.
    info = runtime.inspect_volume(declaration.name)
    assert info is not None
    assert info.in_use_by is not None and len(info.in_use_by) == 1

    # Refuse removal while the box holds the volume.
    with pytest.raises(VolumeInUse):
        runtime.remove_volume(declaration.name)

    # Remove the box and release the volume.
    runtime.remove(plan.project.name)
    released = runtime.inspect_volume(declaration.name)
    assert released is not None
    assert released.in_use_by == ()
    runtime.remove_volume(declaration.name)
    assert runtime.inspect_volume(declaration.name) is None


# Verify create requires declared volumes to be ensured first.
def test_fake_runtime_requires_ensured_volumes_before_create(tmp_path: Path) -> None:
    # Prepare a volume-bearing plan without ensuring its volume.
    declaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    runtime: FakeRuntime = FakeRuntime()
    preparation = runtime.prepare(plan, make_definition())
    artifact: BuildArtifact = BuildArtifact(
        reference = preparation.requirements.artifact.reference,
        platform = None,
        digest = None,
        transport = ArtifactTransport.LOCAL_IMAGE,
        archive_path = None,
        created = False,
    )

    # Require the missing volume to fail before mutation.
    with pytest.raises(Exception) as error:
        runtime.create(preparation, artifact, make_initialization())
    assert type(error.value).__name__ == "VolumeNotFound"
    assert runtime.inspect(plan.project.name) is None


# Verify queued runtime faults surface before the next mutation.
def test_fake_runtime_applies_queued_faults() -> None:
    # Queue a neutral failure.
    runtime: FakeRuntime = FakeRuntime()
    runtime.fail_next(BoxNotReady("demo"))

    # Require the next operation to raise it.
    with pytest.raises(BoxNotReady):
        runtime.ensure_volume("cache")
    assert runtime.ensure_volume_requests == []


# Verify the fake builder rebuilds on request and reuses otherwise.
def test_fake_builder_rebuilds_on_request_and_reuses_otherwise() -> None:
    # Prepare, reuse, and rebuild.
    plan = make_plan()
    sink: RecordingOutputSink = RecordingOutputSink()
    builder: FakeBuilder = FakeBuilder(buildable = True)
    requirement = ArtifactRequirement(reference = "sandbox/build:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)
    first = builder.prepare(plan, make_definition(), requirement, output = sink)
    reused = builder.prepare(plan, make_definition(), requirement, output = sink)
    rebuilt = builder.prepare(plan, make_definition(), requirement, rebuild = True, output = sink)

    # Compare creation and phases.
    assert first.created is True
    assert reused.created is False
    assert rebuilt.created is True
    assert sink.progress_phases == (ProgressPhase.BUILD_IMAGE, ProgressPhase.BUILD_IMAGE)
    assert sink.progress_subjects == ("workspace", "workspace")


# Verify an image-only service is pulled without a build phase.
def test_fake_builder_pulls_an_image_only_service() -> None:
    # Prepare an image-only service.
    plan = make_plan()
    sink: RecordingOutputSink = RecordingOutputSink()
    builder: FakeBuilder = FakeBuilder(buildable = False)
    requirement = ArtifactRequirement(reference = "sandbox/pull:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)
    artifact = builder.prepare(plan, make_definition(), requirement, output = sink)

    # Require a pull report without a build phase.
    assert artifact.created is True
    assert sink.progress_phases == ()

    # Require an explicit rebuild to reuse the present image without pulling again.
    rebuilt = builder.prepare(plan, make_definition(), requirement, rebuild = True, output = sink)
    assert rebuilt.created is False
    assert sink.progress_phases == ()


# Verify the fake builder records the operation-scoped staging request.
def test_fake_builder_records_staging_and_writes_archives(tmp_path: Path) -> None:
    # Prepare a Docker archive.
    plan = make_plan()
    builder: FakeBuilder = FakeBuilder()
    requirement = ArtifactRequirement(reference = "sandbox/archive:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)
    artifact = builder.prepare(plan, make_definition(), requirement, rebuild = True, staging_dir = tmp_path)

    # Compare the archive and the recorded request.
    assert artifact.archive_path is not None and artifact.archive_path.is_file()
    assert artifact.archive_path.is_relative_to(tmp_path)
    assert builder.requests == [
        PrepareRequest(
            plan = plan,
            definition = make_definition(),
            requirement = requirement,
            rebuild = True,
            staging_dir = tmp_path,
        ),
    ]


# Verify an archive transport requires caller-owned staging.
def test_fake_builder_requires_staging_for_archives() -> None:
    # Prepare an archive without a staging directory.
    builder: FakeBuilder = FakeBuilder()
    requirement = ArtifactRequirement(reference = "sandbox/archive:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)
    with pytest.raises(ValueError):
        builder.prepare(make_plan(), make_definition(), requirement)


# Verify the fake builder rejects unsupported transports before preparing an image.
def test_fake_builder_rejects_unsupported_transports_before_preparation() -> None:
    # Reject the OCI archive.
    builder: FakeBuilder = FakeBuilder()
    requirement = ArtifactRequirement(reference = "sandbox/oci:latest", platform = None, transport = ArtifactTransport.OCI_ARCHIVE)
    with pytest.raises(ArtifactRejected):
        builder.prepare(make_plan(), make_definition(), requirement)
    assert builder.images == set()

    # Require a later supported preparation to create the image.
    local = ArtifactRequirement(reference = "sandbox/oci:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)
    artifact = builder.prepare(make_plan(), make_definition(), local)
    assert artifact.created is True


# Verify the fake builder applies queued faults before recording a prepared image.
def test_fake_builder_applies_queued_faults() -> None:
    # Queue a capability failure.
    builder: FakeBuilder = FakeBuilder()
    builder.fail_next(ArtifactRejected(transport = "docker-archive"))
    requirement = ArtifactRequirement(reference = "sandbox/fault:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    # Require the fault before the image exists.
    with pytest.raises(ArtifactRejected):
        builder.prepare(make_plan(), make_definition(), requirement)
    assert builder.images == set()
