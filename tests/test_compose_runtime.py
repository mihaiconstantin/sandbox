"""Verify ComposeRuntime over a scripted Docker engine (T2)."""

# Imports.
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

# Import pytest for fixtures and typed failure assertions.
import pytest

# Import the shared contract scenarios and neutral fixtures.
from port_contract import RuntimeContract, build_matching_artifact
from neutral_fixtures import make_definition, make_plan, make_volume

# Import neutral domain values.
from sandbox.domain import (
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    Mount,
    Provenance,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRef,
    SandboxPlan,
    Secret,
    VolumeDeclaration,
)

# Import the typed public errors under test.
from sandbox.errors.boxes import BoxAmbiguous, BoxNotReady, BoxNotRunning
from sandbox.errors.capabilities import ArtifactRejected, CapabilityError
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.create import CreateFailed, CreatePostconditionFailed
from sandbox.errors.engine import EngineFailure
from sandbox.errors.ownership import OwnershipViolation
from sandbox.errors.prerequisites import PrerequisiteError
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.removal import IncompleteRemoval, NetworkInUse, NothingToRemove
from sandbox.errors.secrets import SecretFileError
from sandbox.errors.terminal import InteractiveTerminalRequired
from sandbox.errors.volumes import VolumeCreateFailed, VolumeInUse, VolumeNotFound, VolumeOwnershipError

# Import the integration under test.
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.compose.runtime import ComposeRuntime
from sandbox.ports.output import OutputChannel
from sandbox.ports.runtime import RuntimePreparation
from sandbox.testing.output import RecordingOutputSink

# Import the scripted engine and its recorded commands.
from compose_runtime_engine import RecordedCommand, ScriptedComposeEngine


# Build one runtime with the requested terminal capability.
def make_runtime(engine: ScriptedComposeEngine, *, terminal: bool = True) -> ComposeRuntime:
    # Return the runtime over the scripted engine.
    return ComposeRuntime(DockerCli(engine), interactive_terminal = lambda: terminal)


# Build one volume-bearing plan and its declaration.
@pytest.fixture
def volume_plan() -> tuple[SandboxPlan, VolumeDeclaration]:
    # Build the plan and its declaration.
    declaration: VolumeDeclaration = make_volume()
    return make_plan(volumes = (declaration,)), declaration


# Build one artifact from a preparation.
def matching_artifact(preparation: RuntimePreparation, directory: Path) -> BuildArtifact:
    # Return the neutral matching artifact.
    return build_matching_artifact(preparation, directory)


# Create one box from a prepared plan.
def create_box(
    runtime: ComposeRuntime,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    directory: Path,
    *,
    initialization: bool = True,
) -> BoxObservation:
    # Prepare the runtime state.
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, directory)

    # Ensure every declared volume.
    for declaration in plan.volumes:
        # Ensure the declared volume.
        runtime.ensure_volume(declaration.name)

    # Plan initialization when requested.
    planned = runtime.plan_initialization(preparation, artifact) if initialization else None

    # Create and return the observation.
    return runtime.create(preparation, artifact, planned)


# Read the single command containing one marker.
def command_with(engine: ScriptedComposeEngine, marker: str) -> RecordedCommand:
    # Return the first matching command.
    for command in engine.commands:
        # If the marker is present.
        if marker in command.arguments:
            # Return the command.
            return command

    # Throw when no command matched.
    raise AssertionError(f"No command contained {marker!r}.")


# Verify the real Compose runtime satisfies the shared T1 scenarios.
class TestComposeRuntimeContract(RuntimeContract):
    # Supply a runtime over a fresh scripted engine.
    @pytest.fixture
    def runtime(self) -> ComposeRuntime:
        # Return the runtime under test.
        return make_runtime(ScriptedComposeEngine())

    # Supply a second independent runtime.
    @pytest.fixture
    def other_runtime(self) -> ComposeRuntime:
        # Return another independent runtime.
        return make_runtime(ScriptedComposeEngine())

    # Supply a runtime configured for one interactive shell status.
    @pytest.fixture
    def runtime_with_enter_status(self) -> Callable[[int], ComposeRuntime]:
        # Return a factory that scripts the requested shell status.
        def make(status: int) -> ComposeRuntime:
            # Script the interactive status on a fresh engine.
            engine: ScriptedComposeEngine = ScriptedComposeEngine()
            engine.enter_status = status
            return make_runtime(engine)

        # Return the runtime factory.
        return make


# Verify preparation projects the neutral requirements without leaking secret files.
def test_prepare_projects_mounts_and_a_local_image_without_secret_mounts(tmp_path: Path) -> None:
    # Build one real secret file.
    secret_path: Path = tmp_path / "token"
    secret_path.write_text("secret value", encoding = "utf-8")

    # Build a plan with one volume and one secret.
    declaration: VolumeDeclaration = make_volume()
    plan = make_plan(volumes = (declaration,), secrets = (Secret(alias = "token", host_path = secret_path),))
    definition = make_definition()

    # Prepare the runtime.
    engine = ScriptedComposeEngine()
    preparation = make_runtime(engine).prepare(plan, definition)

    # Require the neutral requirements.
    assert preparation.requirements.artifact.reference == "sandbox/contract:latest"
    assert preparation.requirements.artifact.transport is ArtifactTransport.LOCAL_IMAGE
    assert preparation.requirements.artifact.platform is None
    assert preparation.requirements.spec.working_directory == plan.workspace.target

    # Require the project and declared volume mounts only.
    targets: set[str] = {mount.target for mount in preparation.requirements.spec.mounts}
    assert targets == {plan.workspace.target, declaration.target}
    assert "/run/secrets/token" not in targets

    # Require secret files to stay separate from the neutral mounts.
    assert all(not mount.target.startswith("/run/secrets/") for mount in preparation.requirements.spec.mounts)

    # Require the override to declare labels, external volumes, and secret files.
    override: str = engine.override_texts[-1]
    assert 'sb.project: "demo"' in override
    assert "external: true" in override
    assert f'file: "{secret_path}"' in override
    assert "pre_start:" not in override


# Verify create uses one no-build, no-pull Compose start and streams child output.
def test_create_uses_no_build_no_pull_and_streams_child_output(tmp_path: Path) -> None:
    # Prepare, plan, and create one box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    sink = RecordingOutputSink()
    create_box_with_sink = _create_with_sink(runtime, plan, definition, tmp_path, sink)

    # Require a live observation.
    assert create_box_with_sink.name == plan.project.name
    assert create_box_with_sink.state.is_live

    # Require the exact no-build, no-pull start.
    up: RecordedCommand = command_with(engine, "up")
    arguments: tuple[str, ...] = up.arguments
    start: int = arguments.index("up")
    assert arguments[start:start + 5] == ("up", "-d", "--no-build", "--pull", "never")
    assert arguments[-1] == definition.service

    # Require the child output to stream on its original channel.
    assert sink.output_bytes(OutputChannel.STDOUT) == b"creating\n"

    # Require the runtime to never build or pull.
    assert not any(command.arguments[:2] == ("docker", "pull") for command in engine.commands)
    assert not any(command.arguments[:2] == ("docker", "compose") and "build" in command.arguments for command in engine.commands)


# Build and create one box while recording output.
def _create_with_sink(runtime: ComposeRuntime, plan: SandboxPlan, definition: RecipeDefinition, directory: Path, sink: RecordingOutputSink) -> BoxObservation:
    # Prepare and build the artifact.
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, directory)

    # Plan initialization and create with the recording sink.
    return runtime.create(preparation, artifact, runtime.plan_initialization(preparation, artifact), output = sink)


# Verify create rejects a mismatched platform or transport before mutation.
def test_create_rejects_platform_and_transport_mismatches(tmp_path: Path) -> None:
    # Script a constrained service platform.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["platform"] = "linux/amd64"
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)

    # Require a platform mismatch rejection.
    with pytest.raises(ArtifactRejected):
        runtime.create(preparation, replace(artifact, platform = "linux/arm64"))

    # Build one archive outside the accepted transport.
    archive: Path = tmp_path / "artifact.tar"
    archive.write_bytes(b"archive")

    # Require a transport mismatch rejection.
    with pytest.raises(ArtifactRejected):
        runtime.create(preparation, replace(artifact, transport = ArtifactTransport.DOCKER_ARCHIVE, archive_path = archive))

    # Require no start after either rejection.
    assert not any("up" in command.arguments for command in engine.commands)


# Verify initialization always probes the UID and filters ineligible volumes.
def test_plan_initialization_always_probes_and_filters_eligible_targets(tmp_path: Path) -> None:
    # Build a plan with one eligible and one ineligible volume.
    eligible: VolumeDeclaration = make_volume(name = "cache", target = "/var/cache/demo")
    ineligible: VolumeDeclaration = make_volume(name = "remote", target = "/var/lib/remote")
    plan = make_plan(volumes = (eligible, ineligible))
    definition = make_definition()

    # Script the physical volumes.
    engine = ScriptedComposeEngine()
    engine.add_managed_volume("cache")
    engine.add_managed_volume("remote", driver = "other")

    # Prepare and plan initialization.
    runtime = make_runtime(engine)
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)
    initialization = runtime.plan_initialization(preparation, artifact)

    # Require the numeric UID and only the eligible target.
    assert initialization.uid == 1000
    assert initialization.targets == ("/var/cache/demo",)

    # Require the probe to forbid implicit pulls.
    probe: RecordedCommand = command_with(engine, "run")
    assert "--pull=never" in probe.arguments
    assert probe.arguments[-1] == "-u"

    # Require a volume-less plan to still resolve the UID.
    empty_engine = ScriptedComposeEngine()
    empty_runtime = make_runtime(empty_engine)
    empty_plan = make_plan()
    empty_preparation = empty_runtime.prepare(empty_plan, definition)
    empty_artifact: BuildArtifact = matching_artifact(empty_preparation, tmp_path)
    empty = empty_runtime.plan_initialization(empty_preparation, empty_artifact)
    assert empty.uid == 1000
    assert empty.targets == ()


# Verify probe failures preserve the engine failure and invalid output is configuration.
def test_probe_failure_and_non_numeric_output(tmp_path: Path) -> None:
    # Prepare one volume-less box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)

    # Script a failed probe.
    engine.probe_returncode = 42
    engine.probe_stderr = b"probe failed\n"
    with pytest.raises(EngineFailure) as failed:
        runtime.plan_initialization(preparation, artifact)
    assert failed.value.failure.exit_code == 42
    assert failed.value.failure.operation == "probe_user"

    # Script non-numeric probe output.
    engine.probe_returncode = 0
    engine.probe_output = b"root\n"
    with pytest.raises(ConfigurationError):
        runtime.plan_initialization(preparation, artifact)

    # Script the reserved all-ones UID.
    engine.probe_output = b"4294967295\n"
    with pytest.raises(ConfigurationError):
        runtime.plan_initialization(preparation, artifact)


# Verify volume creation is idempotent and rejects unmanaged or incomplete volumes.
def test_ensure_volume_rejects_unmanaged_and_incomplete_volumes() -> None:
    # Script one unmanaged and one partially labelled volume.
    engine = ScriptedComposeEngine()
    engine.add_volume("cache")
    engine.add_volume("partial", labels = {"sb.managed": "true", "sb.resource": "volume"})
    runtime = make_runtime(engine)

    # Require unmanaged ownership failures.
    with pytest.raises(VolumeOwnershipError):
        runtime.ensure_volume("cache")
    with pytest.raises(VolumeOwnershipError):
        runtime.ensure_volume("partial")

    # Create one fresh volume and reuse it.
    first = runtime.ensure_volume("fresh")
    second = runtime.ensure_volume("fresh")
    assert first.created is True
    assert second.created is False
    assert engine.volumes["fresh"]["Labels"] == {"sb.managed": "true", "sb.resource": "volume", "sb.scope": "shared"}

    # Script an incomplete creation.
    engine.drop_volume_create = True
    with pytest.raises(VolumeCreateFailed):
        runtime.ensure_volume("phantom")

    # Script a failed creation command.
    engine.volume_create_returncode = 13
    engine.volume_create_stderr = b"create failed\n"
    with pytest.raises(VolumeCreateFailed) as failed:
        runtime.ensure_volume("broken")
    failure = failed.value.failure
    assert failure is not None
    assert failure.exit_code == 13


# Verify volume observation, listing, removal preflight, and postconditions.
def test_volume_inspect_list_and_remove_semantics() -> None:
    # Script two managed volumes and one unmanaged volume.
    engine = ScriptedComposeEngine()
    engine.add_managed_volume("cache")
    engine.add_managed_volume("zebra")
    engine.add_volume("other")
    runtime = make_runtime(engine)

    # Require managed observations and name order.
    cache = runtime.inspect_volume("cache")
    assert cache is not None
    assert cache.driver == "local"
    assert tuple(info.name for info in runtime.list_volumes()) == ("cache", "zebra")
    assert runtime.inspect_volume("missing") is None

    # Require unmanaged ownership rejection.
    with pytest.raises(VolumeOwnershipError):
        runtime.inspect_volume("other")

    # Attach one referencing container.
    identifier: str = engine.add_container(
        labels = {"other": "true"},
        mounts = [{"Type": "volume", "Name": "cache", "Destination": "/var/cache/demo"}],
    )
    referenced = runtime.inspect_volume("cache")
    assert referenced is not None
    assert referenced.in_use_by is not None
    assert len(referenced.in_use_by) == 1

    # Require reference refusal.
    with pytest.raises(VolumeInUse):
        runtime.remove_volume("cache")

    # Release the reference and remove the volume.
    engine.containers.pop(identifier)
    runtime.remove_volume("cache")
    assert runtime.inspect_volume("cache") is None

    # Require a removal postcondition failure.
    engine.add_managed_volume("stuck")
    engine.keep_volume_after_remove = True
    with pytest.raises(IncompleteRemoval):
        runtime.remove_volume("stuck")

    # Require absence proof.
    with pytest.raises(VolumeNotFound):
        runtime.remove_volume("missing")


# Verify invalid physical volume names fail before any engine command.
def test_invalid_volume_names_fail_before_engine_commands() -> None:
    # Build a fresh runtime.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)

    # Require validation before inspection or mutation.
    with pytest.raises(ConfigurationError):
        runtime.ensure_volume("bad name")
    with pytest.raises(ConfigurationError):
        runtime.inspect_volume("bad name")
    with pytest.raises(ConfigurationError):
        runtime.remove_volume("bad name")

    # Require no engine command.
    assert engine.commands == []


# Verify removal preflights external attachments and excludes project-owned containers.
def test_removal_preflights_external_attachments_and_excludes_project_containers(tmp_path: Path) -> None:
    # Create one box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    create_box(runtime, plan, definition, tmp_path)

    # Attach one external container to the project network.
    external: str = engine.add_container(labels = {"external": "true"}, name = "external", networks = ("demo_default",))

    # Require the read-only plan to remain available for the CLI preview.
    planning: RemovalPlan = runtime.plan_removal(plan.project.name)
    assert planning.box == plan.project.name

    # Require the external attachment to block removal before mutation.
    with pytest.raises(NetworkInUse):
        runtime.remove(plan.project.name)
    assert engine.containers

    # Remove the external attachment.
    engine.containers.pop(external)

    # Attach one project-owned hook container.
    engine.add_container(
        labels = {
            "sb.managed": "true",
            "sb.project": "demo",
            "sb.resource": "container",
            "sb.role": "volume-init",
            "com.docker.compose.project": "demo",
        },
        name = "demo-volume-init",
        networks = ("demo_default",),
    )

    # Require a plan that includes both project containers.
    removal: RemovalPlan = runtime.plan_removal(plan.project.name)
    assert len(removal.containers) == 2

    # Require successful removal of both containers and the network.
    runtime.remove(plan.project.name)
    assert engine.containers == {}
    assert engine.networks == {}


# Verify removal refuses project resources without full ownership labels.
def test_removal_refuses_unowned_project_resources() -> None:
    # Script one container that only carries the Compose project label.
    engine = ScriptedComposeEngine()
    engine.add_container(labels = {"com.docker.compose.project": "demo"}, name = "unowned")
    runtime = make_runtime(engine)

    # Require an ownership failure before mutation.
    with pytest.raises(OwnershipViolation):
        runtime.plan_removal("demo")
    with pytest.raises(OwnershipViolation):
        runtime.remove("demo")

    # Require the container to remain.
    assert len(engine.containers) == 1


# Verify removal reports remaining resources after a failed postcondition.
def test_removal_postcondition_reports_remaining_resources(tmp_path: Path) -> None:
    # Create one box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    create_box(runtime, plan, definition, tmp_path)

    # Keep the network after its successful removal command.
    engine.keep_network_after_remove = True

    # Require a postcondition failure.
    with pytest.raises(IncompleteRemoval):
        runtime.remove(plan.project.name)


# Verify removal reports the absence contract.
def test_removal_reports_nothing_to_remove() -> None:
    # Build a fresh runtime.
    runtime = make_runtime(ScriptedComposeEngine())

    # Require the typed absence error.
    with pytest.raises(NothingToRemove):
        runtime.plan_removal("demo")
    with pytest.raises(NothingToRemove):
        runtime.remove("demo")


# Verify enter requires a TTY and normalizes the shell status.
def test_enter_requires_tty_and_normalizes_shell_status(tmp_path: Path) -> None:
    # Create one box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    create_box(runtime, plan, definition, tmp_path)

    # Require the terminal precondition.
    with pytest.raises(InteractiveTerminalRequired):
        make_runtime(engine, terminal = False).enter(plan.project.name, "bash", False)

    # Require signal termination to normalize to one.
    engine.enter_status = -9
    assert runtime.enter(plan.project.name, "bash", False) == 1

    # Require positive shell status preservation.
    engine.enter_status = 7
    assert runtime.enter(plan.project.name, "bash", True) == 7


# Verify a stopped box cannot be entered.
def test_enter_rejects_a_stopped_box(tmp_path: Path) -> None:
    # Create and stop one box.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    create_box(runtime, plan, definition, tmp_path)
    runtime.stop(plan.project.name)

    # Require the typed state failure.
    with pytest.raises(BoxNotRunning):
        runtime.enter(plan.project.name, "bash", False)


# Verify the Compose safety checks run before the builder.
def test_safety_checks_reject_unsafe_labels_hooks_env_files_and_secrets(tmp_path: Path) -> None:
    # Script a missing sandbox label on the realized service.
    engine = ScriptedComposeEngine()
    engine.apply_override_labels = False
    with pytest.raises(ConfigurationError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Script a root recipe hook without permission.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["pre_start"] = [{"user": "0:0"}]
    with pytest.raises(ConfigurationError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Script a privileged recipe hook.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["pre_start"] = [{"privileged": True}]
    with pytest.raises(ConfigurationError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Allow the root hook when the plan permits root.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["pre_start"] = [{"user": "0:0"}]
    make_runtime(engine).prepare(make_plan(allow_root = True), make_definition())

    # Script an environment file outside the project and catalogue.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["env_file"] = ["/outside/env"]
    with pytest.raises(ConfigurationError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Script an undeclared service secret reference.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["secrets"] = ["ghost"]
    with pytest.raises(ConfigurationError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Script an invalid top-level secret declaration.
    engine = ScriptedComposeEngine()
    engine.base_configuration["secrets"] = {"bad": {}}
    with pytest.raises(RecipeUnresolved):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Create one in-project environment file.
    project_directory: Path = tmp_path / "project"
    project_directory.mkdir()
    environment_file: Path = project_directory / "env"
    environment_file.write_text("NAME=value\n", encoding = "utf-8")

    # Require a contained environment file to pass.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["env_file"] = [str(environment_file)]
    make_runtime(engine).prepare(make_plan(directory = project_directory), make_definition())


# Verify the generated initializer restricts its capabilities and targets.
def test_generated_hook_capabilities_and_targets_are_restricted() -> None:
    # Build a volume-bearing plan.
    declaration: VolumeDeclaration = make_volume()
    plan = make_plan(volumes = (declaration,))

    # Script a generated-shaped recipe hook that adds an unsafe capability.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["pre_start"] = [{
        "user": "0:0",
        "labels": {"sb.managed": "true", "sb.project": "demo", "sb.resource": "container", "sb.role": "volume-init"},
        "entrypoint": ["/bin/chown"],
        "command": ["--from=0", "+1000", declaration.target],
        "cap_drop": ["ALL"],
        "cap_add": ["SYS_ADMIN"],
    }]

    # Require the capability rejection.
    with pytest.raises(ConfigurationError) as failed:
        make_runtime(engine).prepare(plan, make_definition())
    assert failed.value.field.endswith(".cap_add")

    # Require a target outside the declared volumes to be rejected.
    engine.base_configuration["services"]["workspace"]["pre_start"][0]["cap_add"] = ["CHOWN"]
    engine.base_configuration["services"]["workspace"]["pre_start"][0]["command"] = ["--from=0", "+1000", "/outside"]
    with pytest.raises(ConfigurationError) as failed:
        make_runtime(engine).prepare(plan, make_definition())
    assert failed.value.field.endswith(".command")


# Verify the healthcheck root guard applies only when initialization targets exist.
def test_healthcheck_root_guard_requires_initialization_targets(tmp_path: Path) -> None:
    # Build a volume-bearing plan.
    declaration: VolumeDeclaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    definition = make_definition()

    # Script an image healthcheck and a managed volume.
    engine = ScriptedComposeEngine()
    engine.healthcheck = {"Test": ["CMD", "true"]}
    engine.add_managed_volume(declaration.name)
    runtime = make_runtime(engine)

    # Prepare and build the artifact.
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)
    initialization = runtime.plan_initialization(preparation, artifact)
    assert initialization.targets

    # Require the guard before the start.
    with pytest.raises(RecipeUnresolved):
        runtime.create(preparation, artifact, initialization)
    assert not any("up" in command.arguments for command in engine.commands)

    # Require a volume-less initialization to skip the guard.
    empty_engine = ScriptedComposeEngine()
    empty_engine.healthcheck = {"Test": ["CMD", "true"]}
    empty_runtime = make_runtime(empty_engine)
    empty_plan = make_plan()
    empty_preparation = empty_runtime.prepare(empty_plan, definition)
    empty_artifact: BuildArtifact = matching_artifact(empty_preparation, tmp_path)
    empty_initialization = empty_runtime.plan_initialization(empty_preparation, empty_artifact)
    observation = empty_runtime.create(empty_preparation, empty_artifact, empty_initialization)
    assert observation.state.is_live


# Verify the generated hook replaces the recipe sequence and stays first.
def test_generated_hook_replaces_and_preserves_recipe_hooks(tmp_path: Path) -> None:
    # Build a volume-bearing plan.
    declaration: VolumeDeclaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    definition = make_definition()

    # Script one recipe hook and one managed volume.
    engine = ScriptedComposeEngine()
    engine.base_configuration["services"]["workspace"]["pre_start"] = [{"command": ["echo", "recipe"]}]
    engine.add_managed_volume(declaration.name)
    runtime = make_runtime(engine)

    # Prepare, plan, and create.
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)
    initialization = runtime.plan_initialization(preparation, artifact)
    runtime.create(preparation, artifact, initialization)

    # Require the final override to replace the sequence with the generated hook first.
    override: str = engine.override_texts[-1]
    assert "pre_start: !override [" in override
    assert '"--from=0"' in override
    assert '"+1000"' in override
    assert declaration.target in override
    assert "recipe" in override

    # Require the realized sequence to carry both hooks in order.
    configuration = engine._effective_configuration(override)
    hooks = configuration["services"]["workspace"]["pre_start"]
    assert hooks[0]["labels"]["sb.role"] == "volume-init"
    assert hooks[1]["command"] == ["echo", "recipe"]


# Verify the runtime requires the supported Compose floor before resolution.
def test_prepare_requires_the_supported_compose_floor() -> None:
    # Script an unsupported Compose version.
    engine = ScriptedComposeEngine()
    engine.compose_version = b"5.5.9\n"

    # Require the typed prerequisite failure before configuration resolution.
    with pytest.raises(PrerequisiteError):
        make_runtime(engine).prepare(make_plan(), make_definition())

    # Require no configuration or mutation command.
    assert not any("config" in command.arguments for command in engine.commands)
    assert not any("up" in command.arguments for command in engine.commands)


# Verify a partially created container is refused before start.
def test_start_refuses_a_partially_created_container() -> None:
    # Script a created container.
    engine = ScriptedComposeEngine()
    engine.add_container(
        labels = {
            "sb.managed": "true",
            "sb.project": "demo",
            "sb.resource": "container",
            "sb.role": "box",
            "com.docker.compose.project": "demo",
            "com.docker.compose.oneoff": "False",
        },
        state = "created",
    )
    runtime = make_runtime(engine)

    # Require the typed not-ready failure without an engine start.
    with pytest.raises(BoxNotReady):
        runtime.start("demo")
    assert not any(command.arguments[:2] == ("docker", "start") for command in engine.commands)


# Verify a changed realized configuration is rejected before the start.
def test_realized_configuration_mismatch_is_rejected(tmp_path: Path) -> None:
    # Build a volume-bearing plan.
    declaration: VolumeDeclaration = make_volume()
    plan = make_plan(volumes = (declaration,))
    definition = make_definition()

    # Script a managed volume and a final-resolution mutation.
    engine = ScriptedComposeEngine()
    engine.add_managed_volume(declaration.name)
    engine.mutate_on_final = {"working_dir": "/elsewhere"}
    runtime = make_runtime(engine)

    # Prepare and build the artifact.
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)
    initialization = runtime.plan_initialization(preparation, artifact)

    # Require the realized verification failure.
    with pytest.raises(RecipeUnresolved) as failed:
        runtime.create(preparation, artifact, initialization)
    assert "working_directory" in str(failed.value)
    assert not any("up" in command.arguments for command in engine.commands)


# Verify secret sources must be readable regular files before any engine command.
def test_secret_files_must_be_readable_regular_files(tmp_path: Path) -> None:
    # Use a missing secret source.
    plan = make_plan(secrets = (Secret(alias = "token", host_path = tmp_path / "missing"),))

    # Require the typed secret-file error before any engine command.
    engine = ScriptedComposeEngine()
    with pytest.raises(SecretFileError):
        make_runtime(engine).prepare(plan, make_definition())
    assert engine.commands == []

    # Use a directory as a secret source.
    plan = make_plan(secrets = (Secret(alias = "token", host_path = tmp_path),))
    with pytest.raises(SecretFileError):
        make_runtime(engine).prepare(plan, make_definition())

    # Use an unreadable secret source.
    unreadable: Path = tmp_path / "unreadable"
    unreadable.write_text("secret", encoding = "utf-8")
    unreadable.chmod(0o000)
    try:
        # Require the readability failure when the process cannot read the file.
        if not unreadable.is_file() or not _readable(unreadable):
            # Build the plan with the unreadable secret.
            plan = make_plan(secrets = (Secret(alias = "token", host_path = unreadable),))
            with pytest.raises(SecretFileError):
                make_runtime(ScriptedComposeEngine()).prepare(plan, make_definition())
    finally:
        # Restore permissions for cleanup.
        unreadable.chmod(0o600)


# Report whether the current process can read one file.
def _readable(path: Path) -> bool:
    # Read the access flag.
    import os

    # Return the read-access result.
    return os.access(path, os.R_OK)


# Verify observation maps state, mounts, networks, provenance, and nullables.
def test_observation_maps_state_mounts_networks_and_nullables() -> None:
    # Script one managed container with a project bind and a volume.
    engine = ScriptedComposeEngine()
    engine.add_container(
        labels = {
            "sb.managed": "true",
            "sb.project": "demo",
            "sb.resource": "container",
            "sb.role": "box",
            "sb.catalogue": "default",
            "sb.recipe": "base",
            "com.docker.compose.project": "demo",
            "com.docker.compose.oneoff": "False",
        },
        state = "restarting",
        mounts = [
            {"Type": "bind", "Source": "/work/demo", "Destination": "/projects/demo"},
            {"Type": "volume", "Name": "cache", "Destination": "/var/cache/demo"},
        ],
        networks = ("demo_default",),
    )
    runtime = make_runtime(engine)

    # Read the observation.
    observation = runtime.inspect("demo")
    assert observation is not None
    assert observation.state is BoxState.STARTING
    assert observation.status_text == "restarting"
    assert observation.provenance == Provenance(catalogue = "default", recipe = "base")
    assert observation.workspace is not None
    assert observation.workspace.host_directory == Path("/work/demo")
    assert observation.mounts is not None
    assert Mount(kind = "volume", source = "cache", target = "/var/cache/demo") in observation.mounts
    assert observation.networks is not None
    assert observation.networks[0].name == "demo_default"
    assert observation.backend is not None and observation.backend.id

    # Script a container with unavailable mounts and networks and an unknown status.
    engine.containers.clear()
    engine.add_container(labels = {"sb.managed": "true", "sb.project": "demo", "sb.role": "box", "com.docker.compose.project": "demo", "com.docker.compose.oneoff": "False"}, state = "unexpected")
    unknown = runtime.inspect("demo")
    assert unknown is not None
    assert unknown.state is BoxState.UNKNOWN
    assert unknown.mounts is not None
    assert unknown.networks is not None


# Verify listing reports ambiguity and sorted managed observations.
def test_list_is_sorted_and_reports_ambiguity() -> None:
    # Script two projects.
    engine = ScriptedComposeEngine()
    engine.add_container(labels = {"sb.managed": "true", "sb.project": "zulu", "sb.role": "box", "com.docker.compose.project": "zulu", "com.docker.compose.oneoff": "False"}, name = "zulu-1")
    engine.add_container(labels = {"sb.managed": "true", "sb.project": "alpha", "sb.role": "box", "com.docker.compose.project": "alpha", "com.docker.compose.oneoff": "False"}, name = "alpha-1")
    runtime = make_runtime(engine)

    # Require name order.
    assert tuple(observation.name for observation in runtime.list()) == ("alpha", "zulu")

    # Script a second container for one project.
    engine.add_container(labels = {"sb.managed": "true", "sb.project": "alpha", "sb.role": "box", "com.docker.compose.project": "alpha", "com.docker.compose.oneoff": "False"}, name = "alpha-2")

    # Require the ambiguity failure.
    with pytest.raises(BoxAmbiguous):
        runtime.list()


# Verify a missing primary service is a recipe error.
def test_prepare_requires_the_primary_service() -> None:
    # Script a configuration without the selected service.
    engine = ScriptedComposeEngine()
    engine.base_configuration = {"services": {}, "networks": {"default": {}}}

    # Require the recipe failure.
    with pytest.raises(RecipeUnresolved):
        make_runtime(engine).prepare(make_plan(), make_definition())


# Verify a failed start preserves its command facts.
def test_create_failure_preserves_command_facts(tmp_path: Path) -> None:
    # Prepare one box and script a failed start.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)
    engine.up_returncode = 17
    engine.up_stderr = b"compose up failed\n"

    # Require the typed create failure.
    with pytest.raises(CreateFailed) as failed:
        runtime.create(preparation, artifact)
    assert failed.value.failure.exit_code == 17
    assert failed.value.failure.diagnostic == "compose up failed"


# Verify a missing post-create observation is a typed creation failure.
def test_create_postcondition_requires_an_observed_box(tmp_path: Path) -> None:
    # Prepare one box and script a start without a container.
    engine = ScriptedComposeEngine()
    engine.create_no_container = True
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)

    # Require the typed postcondition failure.
    with pytest.raises(CreatePostconditionFailed):
        runtime.create(preparation, artifact)


# Verify foreign tokens and artifacts are rejected before any engine command.
def test_foreign_token_and_artifact_are_rejected_before_mutation(tmp_path: Path) -> None:
    # Build two independent runtimes.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    foreign = make_runtime(ScriptedComposeEngine())
    plan = make_plan()
    definition = make_definition()

    # Read a foreign preparation.
    preparation = foreign.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)

    # Require the foreign token rejection.
    with pytest.raises(CapabilityError):
        runtime.create(preparation, artifact)

    # Prepare locally and require an artifact reference rejection.
    local = runtime.prepare(plan, definition)
    engine.commands.clear()
    with pytest.raises(ArtifactRejected):
        runtime.create(local, replace(artifact, reference = "sandbox/other:latest"))

    # Require no mutation.
    assert engine.commands == []


# Verify create works without a prior initialization plan.
def test_create_without_initialization_uses_the_base_override(tmp_path: Path) -> None:
    # Prepare and create without an initialization.
    engine = ScriptedComposeEngine()
    runtime = make_runtime(engine)
    plan = make_plan()
    definition = make_definition()
    preparation = runtime.prepare(plan, definition)
    artifact: BuildArtifact = matching_artifact(preparation, tmp_path)

    # Require a live observation.
    observation = runtime.create(preparation, artifact)
    assert observation.state.is_live
    assert any("up" in command.arguments for command in engine.commands)


# Verify returned references remain observation data only.
def test_observations_expose_neutral_runtime_references() -> None:
    # Script one managed container.
    engine = ScriptedComposeEngine()
    identifier: str = engine.add_container(
        labels = {"sb.managed": "true", "sb.project": "demo", "sb.role": "box", "com.docker.compose.project": "demo", "com.docker.compose.oneoff": "False"},
        name = "demo-1",
    )
    runtime = make_runtime(engine)

    # Require a neutral reference.
    observation = runtime.inspect("demo")
    assert observation is not None
    assert observation.backend == RuntimeRef(id = identifier, name = "demo-1")
