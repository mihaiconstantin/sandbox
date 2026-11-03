"""Verify box creation ordering, policy, secrecy, artifacts, and lifecycle through the SDK."""

# Imports.
from dataclasses import replace
from pathlib import Path

import pytest

# Import domain values.
from sandbox.domain.artifact import ArtifactTransport, BuildArtifact
from sandbox.domain.observation import BoxState
from sandbox.domain.volume import VolumeDeclaration

# Import typed errors from their public submodules.
from sandbox.errors.base import CommandFailure, SandboxError
from sandbox.errors.build import BuildFailed
from sandbox.errors.capabilities import ArtifactRejected
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.removal import NetworkInUse
from sandbox.errors.secrets import MissingSecret
from sandbox.errors.volumes import VolumeOwnershipError

# Import the output vocabulary and recording sink.
from sandbox.ports.output import OutputChannel, ProgressPhase
from sandbox.testing.output import RecordingOutputSink

# Import the public SDK.
from sandbox.sdk import CreateBoxRequest, CreateBoxResult, SandboxClient

# Import the test fixtures.
from sdk_fixtures import (
    FAKE_IMAGE,
    RecordingBuilder,
    RecordingRuntime,
    bind_secret,
    make_client,
    make_observation,
    make_requirements,
    manifest_for,
    write_catalogue,
)


# Prepare one temporary home, project directory, and registered catalogue.
def prepare_home(tmp_path: Path, *, volume: bool = True, secret: bool = False) -> tuple[Path, Path]:
    # Create the configuration home and catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    write_catalogue(home, volume = volume, secret = secret)

    # Create the project directory.
    project: Path = tmp_path / "project"
    project.mkdir()
    return home, project


# Build the declared volume matching the fixture manifest.
def fixture_volume() -> VolumeDeclaration:
    # Return the fixed volume declaration.
    return VolumeDeclaration(name = "example-state", scope = "shared", target = "/home/example/.state")


# Verify a successful create returns the effective recipe and observation.
def test_create_returns_effective_recipe_and_observation(tmp_path: Path) -> None:
    # Prepare the public dependencies.
    home: Path
    project: Path
    home, project = prepare_home(tmp_path)
    runtime: RecordingRuntime = RecordingRuntime([])
    builder: RecordingBuilder = RecordingBuilder([])
    client: SandboxClient = make_client(home, runtime = runtime, builder = builder)

    # Create the box.
    result: CreateBoxResult = client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the effective recipe and post-create observation.
    assert result.recipe == "base"
    assert result.box.name == "demo"
    assert result.box.state is BoxState.RUNNING
    assert result.box.image == FAKE_IMAGE
    assert result.box.workspace is not None
    assert result.box.workspace.target == "/projects/demo"

    # Require the builder requirement and ensured volume.
    assert builder.requests[0].requirement.reference == FAKE_IMAGE
    assert builder.requests[0].rebuild is False
    assert runtime.ensure_volume_requests == ["example-state"]
    assert runtime.initialization_requests[0].artifact.reference == FAKE_IMAGE
    assert runtime.create_requests[0].initialization is not None
    assert runtime.create_requests[0].initialization.uid == 1000


# Verify the create order around the two ports.
def test_create_order_is_runtime_policy_builder_volume_initialization_create(tmp_path: Path) -> None:
    # Prepare an ordered event log.
    home, project = prepare_home(tmp_path)
    events: list[str] = []
    client = make_client(home, runtime = RecordingRuntime(events), builder = RecordingBuilder(events))

    # Create the box.
    client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the observable order.
    assert events == [
        "runtime.prepare",
        "builder.prepare",
        "runtime.ensure_volume:example-state",
        "runtime.plan_initialization",
        "runtime.create",
    ]


# Verify missing secrets raise before any runtime or builder mutation.
def test_missing_secret_raises_typed_error_without_mutation(tmp_path: Path) -> None:
    # Prepare a catalogue that requires one unbound secret.
    home, project = prepare_home(tmp_path, volume = False, secret = True)
    runtime = RecordingRuntime([])
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Refuse the create with the structured missing-secret error.
    with pytest.raises(MissingSecret) as raised:
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the structured facts and no mutation.
    assert raised.value.catalogue == "default"
    assert raised.value.alias == "example-secret"
    assert raised.value.recipe == "base"
    assert runtime.prepare_requests == []
    assert builder.requests == []
    assert runtime.ensure_volume_requests == []
    assert runtime.create_requests == []


# Verify a bound secret is resolved into the neutral plan.
def test_bound_secret_is_resolved_into_the_plan(tmp_path: Path) -> None:
    # Bind the required secret.
    home, project = prepare_home(tmp_path, volume = False, secret = True)
    secret_file: Path = bind_secret(home)
    runtime = RecordingRuntime([])
    client = make_client(home, runtime = runtime)

    # Create with the resolved binding.
    client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the resolved host path in the neutral plan.
    assert runtime.prepare_requests[0].plan.secrets[0].alias == "example-secret"
    assert runtime.prepare_requests[0].plan.secrets[0].host_path == secret_file


# Verify neutral policy rejects an invalid spec before the builder or any volume.
def test_invalid_spec_fails_before_builder_and_volumes(tmp_path: Path) -> None:
    # Prepare requirements that policy rejects.
    home, project = prepare_home(tmp_path)
    requirements = make_requirements("demo", project, volumes = (fixture_volume(),))
    requirements = replace(requirements, spec = replace(requirements.spec, privileged = True))
    runtime = RecordingRuntime([], requirements = requirements)
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the policy failure.
    with pytest.raises(ConfigurationError):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require no builder or volume side effect.
    assert builder.requests == []
    assert runtime.ensure_volume_requests == []
    assert runtime.initialization_requests == []


# Verify a build failure creates no volume.
def test_build_failure_creates_no_volume(tmp_path: Path) -> None:
    # Prepare a failing builder.
    home, project = prepare_home(tmp_path)
    runtime = RecordingRuntime([])
    builder = RecordingBuilder([])
    builder.fail_next(BuildFailed(CommandFailure(backend = "docker", operation = "build", command = ("docker", "build"), exit_code = 1, diagnostic = "boom")))
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the build error.
    with pytest.raises(BuildFailed):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require runtime preparation but no volume or create side effect.
    assert len(runtime.prepare_requests) == 1
    assert runtime.ensure_volume_requests == []
    assert runtime.create_requests == []


# Verify UID 0 without allow_root is rejected on the volume-less path.
def test_volume_less_uid_zero_is_rejected_before_create(tmp_path: Path) -> None:
    # Prepare a volume-less catalogue and a root fake runtime.
    home, project = prepare_home(tmp_path, volume = False)
    runtime = RecordingRuntime([], uid = 0)
    client = make_client(home, runtime = runtime)

    # Require the root-policy error.
    with pytest.raises(RootExecutionNotAllowed):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require initialization planning but no create.
    assert len(runtime.initialization_requests) == 1
    assert runtime.ensure_volume_requests == []
    assert runtime.create_requests == []


# Verify UID 0 without allow_root is rejected on the volume path after the build and ensure.
def test_volume_uid_zero_is_rejected_before_create(tmp_path: Path) -> None:
    # Prepare a volume catalogue and a root fake runtime.
    home, project = prepare_home(tmp_path)
    runtime = RecordingRuntime([], uid = 0)
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the root-policy error.
    with pytest.raises(RootExecutionNotAllowed):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the retained image and volume but no create.
    assert len(builder.requests) == 1
    assert runtime.ensure_volume_requests == ["example-state"]
    assert runtime.create_requests == []


# Verify an unmanaged-volume ownership failure propagates before create.
def test_unmanaged_volume_failure_propagates_before_create(tmp_path: Path) -> None:
    # Prepare a runtime that refuses unmanaged volume reuse.
    class RefusingRuntime(RecordingRuntime):
        def ensure_volume(self, name: str):
            raise VolumeOwnershipError(name)

    home, project = prepare_home(tmp_path)
    runtime = RefusingRuntime([])
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the typed ownership failure.
    with pytest.raises(VolumeOwnershipError) as raised:
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the volume identity and no create.
    assert raised.value.name == "example-state"
    assert len(builder.requests) == 1
    assert runtime.create_requests == []


# Verify invalid initialization targets are rejected before create.
def test_invalid_initialization_targets_fail_before_create(tmp_path: Path) -> None:
    # Prepare a fake runtime that plans an undeclared target.
    home, project = prepare_home(tmp_path)
    runtime = RecordingRuntime([], initialization_targets = ("/not-declared",))
    client = make_client(home, runtime = runtime)

    # Require the initialization policy failure.
    with pytest.raises(ConfigurationError) as raised:
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the target field and no create.
    assert raised.value.field == "initialization.targets"
    assert runtime.create_requests == []


# Verify a mismatched builder artifact is rejected before volume mutation.
def test_artifact_mismatch_is_rejected_before_volumes(tmp_path: Path) -> None:
    # Prepare a builder that returns a different image reference.
    class MismatchedBuilder(RecordingBuilder):
        def prepare(self, plan, definition, requirement, **options) -> BuildArtifact:
            artifact = super().prepare(plan, definition, requirement, **options)
            return replace(artifact, reference = "other/image:latest")

    home, project = prepare_home(tmp_path)
    runtime = RecordingRuntime([])
    builder = MismatchedBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the typed artifact rejection.
    with pytest.raises(ArtifactRejected):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require no volume or create side effect.
    assert runtime.ensure_volume_requests == []
    assert runtime.create_requests == []


# Verify archive staging is created for the builder and removed after success.
def test_archive_staging_is_cleaned_up_after_success(tmp_path: Path) -> None:
    # Prepare an archive-capable runtime.
    home, project = prepare_home(tmp_path)
    requirements = make_requirements("demo", project, volumes = (fixture_volume(),), transport = ArtifactTransport.DOCKER_ARCHIVE)
    runtime = RecordingRuntime([], requirements = requirements)
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Create the box.
    client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the archive to have existed during the create and cleanup afterwards.
    staging: Path | None = builder.requests[0].staging_dir
    archive: Path | None = runtime.create_requests[0].artifact.archive_path
    assert staging is not None
    assert archive is not None
    assert not archive.exists()
    assert not staging.exists()


# Verify archive staging is removed after a post-build policy failure.
def test_archive_staging_is_cleaned_up_after_failure(tmp_path: Path) -> None:
    # Prepare an archive-capable runtime whose UID violates the root policy.
    home, project = prepare_home(tmp_path)
    requirements = make_requirements("demo", project, volumes = (fixture_volume(),), transport = ArtifactTransport.DOCKER_ARCHIVE)
    runtime = RecordingRuntime([], requirements = requirements, uid = 0)
    builder = RecordingBuilder([])
    client = make_client(home, runtime = runtime, builder = builder)

    # Require the root-policy error.
    with pytest.raises(RootExecutionNotAllowed):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require the staging directory and its archive to be gone.
    staging: Path | None = builder.requests[0].staging_dir
    assert staging is not None
    assert not staging.exists()


# Verify the output phases and conditional build phase.
def test_output_phases_include_build_only_on_an_actual_build(tmp_path: Path) -> None:
    # Prepare a builder that reuses a present image.
    home, project = prepare_home(tmp_path)
    output = RecordingOutputSink()
    builder = RecordingBuilder([])
    builder.images.add(FAKE_IMAGE)
    client = make_client(home, builder = builder, output = output)

    # Create with a reused image.
    client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require no build phase on reuse.
    assert output.progress_phases == (
        ProgressPhase.PREPARE_IMAGE,
        ProgressPhase.ENSURE_VOLUME,
        ProgressPhase.CREATE,
    )

    # Create with a fresh image and require the build phase.
    fresh_output = RecordingOutputSink()
    fresh_builder = RecordingBuilder([])
    fresh_client = make_client(home, builder = fresh_builder, output = fresh_output)
    fresh_client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))
    assert fresh_output.progress_phases == (
        ProgressPhase.PREPARE_IMAGE,
        ProgressPhase.BUILD_IMAGE,
        ProgressPhase.ENSURE_VOLUME,
        ProgressPhase.CREATE,
    )


# Verify child output is forwarded unchanged and secret contents never enter progress.
def test_process_output_preserves_channel_and_bytes(tmp_path: Path) -> None:
    # Prepare a fake runtime that emits child output.
    home, project = prepare_home(tmp_path)
    output = RecordingOutputSink()
    runtime = RecordingRuntime([], create_output = ((OutputChannel.STDERR, b"child\n"),))
    client = make_client(home, runtime = runtime, output = output)

    # Create the box.
    client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))

    # Require exact channel and bytes.
    assert output.output_events[0].channel is OutputChannel.STDERR
    assert output.output_bytes(OutputChannel.STDERR) == b"child\n"
    assert all("not displayed" not in (subject or "") for subject in output.progress_subjects)


# Verify box lifecycle operations expose neutral results and phases.
def test_box_lifecycle_operations(tmp_path: Path) -> None:
    # Seed two boxes in different states.
    home = tmp_path / "home"
    home.mkdir()
    runtime = RecordingRuntime([])
    runtime.add_box(make_observation("beta", state = BoxState.STOPPED))
    runtime.add_box(make_observation("alpha", state = BoxState.RUNNING))
    output = RecordingOutputSink()
    client = make_client(home, runtime = runtime, output = output)

    # Require lookup and sorted listing.
    assert client.boxes.get("alpha") is not None
    assert client.boxes.get("missing") is None
    assert [box.name for box in client.boxes.list()] == ["alpha", "beta"]

    # Require lifecycle delegation and phases.
    assert client.boxes.start("beta") is True
    assert client.boxes.start("alpha") is False
    assert client.boxes.stop("alpha") is True
    assert output.progress_phases == (ProgressPhase.START, ProgressPhase.START, ProgressPhase.STOP)

    # Require interactive status delegation without output.
    status: int = client.boxes.enter("beta", shell = "/bin/sh", login = True)
    assert status == 0
    assert runtime.enter_requests[0].shell == "/bin/sh"
    assert runtime.enter_requests[0].login is True
    assert output.progress_phases == (ProgressPhase.START, ProgressPhase.START, ProgressPhase.STOP)

    # Require silent removal preview and the removal phase.
    assert client.boxes.plan_removal("alpha").box == "alpha"
    assert output.progress_phases == (ProgressPhase.START, ProgressPhase.START, ProgressPhase.STOP)
    client.boxes.remove("alpha")
    assert output.progress_phases[-1] is ProgressPhase.REMOVE
    assert client.boxes.get("alpha") is None

    # Require runtime state errors to cross as public sandbox errors.
    with pytest.raises(SandboxError):
        client.boxes.stop("missing")


# Verify runtime removal preflight failures cross unchanged and leave the box intact.
def test_remove_propagates_preflight_failure(tmp_path: Path) -> None:
    # Prepare a runtime that refuses removal while a network is attached.
    class AttachedNetworkRuntime(RecordingRuntime):
        def remove(self, name: str) -> None:
            raise NetworkInUse("sandbox-demo-default")

    home = tmp_path / "home"
    home.mkdir()
    runtime = AttachedNetworkRuntime([])
    runtime.add_box(make_observation("demo"))
    output = RecordingOutputSink()
    client = make_client(home, runtime = runtime, output = output)

    # Require the typed removal failure and the retained box.
    with pytest.raises(NetworkInUse):
        client.boxes.remove("demo")
    assert client.boxes.get("demo") is not None
    assert output.progress_phases == (ProgressPhase.REMOVE,)


# Verify unknown catalogues and manifest-name mismatches fail before any port call.
def test_create_rejects_unknown_catalogue_and_manifest_mismatch(tmp_path: Path) -> None:
    # Prepare a home with a registered catalogue.
    home, project = prepare_home(tmp_path)
    client = make_client(home)

    # Require an unknown catalogue to fail cleanly.
    with pytest.raises(RegistryError):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "missing"))

    # Rewrite the manifest under a different name.
    (home / "catalogues" / "default" / "catalogue.toml").write_text(
        manifest_for("other", volume = True, secret = False),
        encoding = "utf-8",
    )

    # Require the manifest/registration mismatch to fail cleanly.
    with pytest.raises(RecipeUnresolved):
        client.boxes.create(CreateBoxRequest(project = "demo", project_dir = project, catalogue = "default"))
