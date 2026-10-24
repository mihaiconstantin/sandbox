"""Verify DockerBuilder over a scripted process runner (T2)."""

# Imports.
import io
import json
import os
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import pytest for fixtures and typed failure assertions.
import pytest

# Import the contract scenario set and neutral fixtures.
from port_contract import BuilderContract
from neutral_fixtures import make_plan

# Import neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BuildArtifact,
    RecipeDefinition,
    SandboxPlan,
)

# Import the typed public errors under test.
from sandbox.errors.build import BuildFailed
from sandbox.errors.capabilities import ArtifactRejected
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.engine import EngineFailure
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Import the integration values under test.
from sandbox.integrations.docker.builder import DockerBuilder
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult, DIAGNOSTIC_LIMIT
from sandbox.ports.output import OutputChannel, ProgressPhase, SILENT
from sandbox.testing.output import RecordingOutputSink


# Record one command received by the scripted runner.
@dataclass(frozen = True, slots = True)
class RecordedCommand:
    # Record the argument vector.
    arguments: tuple[str, ...]

    # Record the environment supplied by the integration.
    environment: Mapping[str, str] | None

    # Report whether complete output was requested.
    capture: bool


# Answer Docker and Compose commands from deterministic scripted state.
class ScriptedProcessRunner:
    # Construct a runner with one built-service configuration.
    def __init__(self, catalogue: Path, *, project: str = "demo", service: str = "workspace") -> None:
        # Record the fixture roots.
        self.catalogue: Path = catalogue
        self.project: str = project
        self.service: str = service

        # Record every command in order.
        self.commands: list[RecordedCommand] = []

        # Record the scripted image store.
        self.images: dict[str, dict[str, Any]] = {}

        # Record the effective service configuration.
        self.configuration: dict[str, Any] = {
            "services": {
                service: {
                    "image": "sandbox/contract:latest",
                    "build": {
                        "context": str(catalogue / "context"),
                        "dockerfile": "Dockerfile",
                        "args": ["BASE=ubuntu"],
                    },
                },
            },
        }

        # Record the version responses.
        self.compose_version: bytes = b"5.6.0\n"
        self.compose_returncode: int = 0
        self.compose_stderr: bytes = b""
        self.buildx_version: bytes = b"github.com/docker/buildx v0.17.0 abcdef\n"
        self.buildx_returncode: int = 0
        self.buildx_stderr: bytes = b""

        # Record the build and pull responses.
        self.build_returncode: int = 0
        self.build_stderr: bytes = b""
        self.pull_returncode: int = 0
        self.pull_stderr: bytes = b""

        # Record the image inspection facts.
        self.architecture: str = "amd64"
        self.operating_system: str = "linux"
        self.config_id: str = "sha256:config-id"
        self.repo_digest: str | None = "sha256:manifest-digest"

        # Record the archive export behavior.
        self.save_returncode: int = 0
        self.save_stderr: bytes = b""
        self.save_tags: list[str] | None = None
        self.save_images: int = 1

    # Read the effective service image reference.
    @property
    def image(self) -> str:
        # Return the configured image or the Compose default.
        service: Mapping[str, Any] = self.configuration["services"][self.service]
        return service.get("image") or f"{self.project}-{self.service}"

    # Add one image to the scripted local store.
    def add_image(self, reference: str | None = None) -> None:
        # Use the effective service image by default.
        image: str = reference or self.image

        # Build the inspection payload.
        repository: str = image.split("@", 1)[0].rsplit(":", 1)[0] if ":" in image.rsplit("/", 1)[-1] else image
        payload: dict[str, Any] = {
            "Id": self.config_id,
            "RepoDigests": [] if self.repo_digest is None else [f"{repository}@{self.repo_digest}"],
            "Os": self.operating_system,
            "Architecture": self.architecture,
            "Variant": None,
        }

        # Record the image.
        self.images[image] = payload

    # Run one scripted Docker or Compose command.
    def run(
        self,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        capture: bool = True,
        output: Any = SILENT,
    ) -> CommandResult:
        # Normalize and record the invocation.
        command: tuple[str, ...] = tuple(arguments)
        self.commands.append(RecordedCommand(arguments = command, environment = environment, capture = capture))

        # Answer the Compose version probe.
        if command[:3] == ("docker", "compose", "version"):
            # Return the scripted version response.
            return CommandResult(command, self.compose_returncode, self.compose_version, self.compose_stderr)

        # Answer the Buildx version probe.
        if command[:3] == ("docker", "buildx", "version"):
            # Return the scripted version response.
            return CommandResult(command, self.buildx_returncode, self.buildx_version, self.buildx_stderr)

        # Answer Compose configuration and build commands.
        if command[:2] == ("docker", "compose"):
            # Resolve the configuration.
            if "config" in command:
                # Return the scripted effective service.
                return CommandResult(command, 0, json.dumps(self.configuration).encode("utf-8"), b"")

            # Build the selected service.
            if "build" in command:
                # Emit one deterministic stderr chunk when the build starts.
                output.process_output(OutputChannel.STDERR, b"build output\n")

                # Mark the image present after a successful build.
                if self.build_returncode == 0:
                    # Record the built image.
                    self.add_image()

                # Return the scripted build result.
                return CommandResult(command, self.build_returncode, b"", self.build_stderr)

        # Answer image inspections and exports.
        if command[:3] == ("docker", "image", "inspect"):
            # Read the inspected reference.
            reference: str = command[-1]

            # Report absence for an unknown image.
            if reference not in self.images:
                # Return Docker's missing-image diagnostic.
                return CommandResult(command, 1, b"", f"Error response from daemon: No such image: {reference}".encode("utf-8"))

            # Return the scripted inspection array.
            return CommandResult(command, 0, json.dumps([self.images[reference]]).encode("utf-8"), b"")

        # Answer the archive export.
        if command[:3] == ("docker", "image", "save"):
            # Read the requested output path.
            destination: Path = Path(command[command.index("--output") + 1])

            # Return a scripted failure without writing an archive.
            if self.save_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.save_returncode, b"", self.save_stderr)

            # Write one valid uncompressed Docker archive.
            self._write_archive(destination)

            # Return success.
            return CommandResult(command, 0, b"", b"")

        # Answer image pulls.
        if command[:2] == ("docker", "pull"):
            # Emit one deterministic pull chunk.
            output.process_output(OutputChannel.STDOUT, b"pull output\n")

            # Mark the image present after a successful pull.
            if self.pull_returncode == 0:
                # Record the pulled image.
                self.add_image()

            # Return the scripted pull result.
            return CommandResult(command, self.pull_returncode, b"", self.pull_stderr)

        # Reject an unexpected command.
        raise AssertionError(f"Unexpected command: {command}")

    # Run one inherited-stdio command.
    def run_interactive(
        self,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
    ) -> CommandResult:
        # Reject interactive use in the builder tests.
        raise AssertionError(f"Unexpected interactive command: {tuple(arguments)}")

    # Write one valid single-image Docker archive.
    def _write_archive(self, destination: Path) -> None:
        # Select the manifest tags.
        tags: list[str] = self.save_tags if self.save_tags is not None else [self.image]

        # Serialize the requested number of image manifests.
        manifest: bytes = json.dumps([
            {
                "Config": f"config-{index}.json",
                "RepoTags": tags,
                "Layers": [],
            }
            for index in range(self.save_images)
        ]).encode("utf-8")

        # Write an uncompressed tar with one manifest member.
        with tarfile.open(destination, mode = "w") as archive:
            # Add the manifest entry.
            info: tarfile.TarInfo = tarfile.TarInfo("manifest.json")
            info.size = len(manifest)
            archive.addfile(info, io.BytesIO(manifest))


# Build one scripted catalogue with a real local build context.
@pytest.fixture
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # Allocate a temporary catalogue root.
    root: Path = tmp_path_factory.mktemp("catalogue")

    # Create the contained build context and Dockerfile.
    context: Path = root / "context"
    context.mkdir()
    (context / "Dockerfile").write_text("FROM scratch\n", encoding = "utf-8")

    # Create the Compose source file.
    (root / "compose.yaml").write_text("services: {}\n", encoding = "utf-8")

    # Return the fixture root.
    return root


# Build one scripted process runner.
@pytest.fixture
def runner(catalogue: Path) -> ScriptedProcessRunner:
    # Return a fresh scripted runner.
    return ScriptedProcessRunner(catalogue)


# Build one real DockerBuilder over the scripted runner.
@pytest.fixture
def builder(runner: ScriptedProcessRunner) -> DockerBuilder:
    # Return the builder under test.
    return DockerBuilder(DockerCli(runner))


# Build one sandbox plan for the builder.
@pytest.fixture
def plan() -> SandboxPlan:
    # Return a volume-less plan.
    return make_plan(directory = Path("/work/demo"))


# Build one opaque recipe definition pointing at the scripted catalogue.
@pytest.fixture
def definition(catalogue: Path) -> RecipeDefinition:
    # Return the standard recipe source.
    return RecipeDefinition(
        catalogue = "default",
        recipe = "base",
        catalogue_root = catalogue,
        files = (catalogue / "compose.yaml",),
        service = "workspace",
    )


# Build one local-image requirement matching the scripted service.
@pytest.fixture
def requirement() -> ArtifactRequirement:
    # Return the local-image requirement.
    return ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)


# Verify the real builder satisfies the shared T1 builder scenarios.
class TestDockerBuilderContract(BuilderContract):
    # Supply the scripted builder.
    @pytest.fixture
    def builder(self, runner: ScriptedProcessRunner) -> DockerBuilder:
        # Return the builder under test.
        return DockerBuilder(DockerCli(runner))

    # Supply the scripted catalogue plan.
    @pytest.fixture
    def plan(self) -> SandboxPlan:
        # Return a volume-less plan.
        return make_plan(directory = Path("/work/demo"))

    # Supply the scripted recipe definition.
    @pytest.fixture
    def definition(self, catalogue: Path) -> RecipeDefinition:
        # Return the standard recipe source.
        return RecipeDefinition(
            catalogue = "default",
            recipe = "base",
            catalogue_root = catalogue,
            files = (catalogue / "compose.yaml",),
            service = "workspace",
        )

    # Supply the matching local-image requirement.
    @pytest.fixture
    def requirement(self) -> ArtifactRequirement:
        # Return the local-image requirement.
        return ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)


# Verify the real builder satisfies the shared scenarios for an image-only service.
class TestDockerImageOnlyBuilderContract(BuilderContract):
    # Supply an image-only scripted runner.
    @pytest.fixture
    def runner(self, catalogue: Path) -> ScriptedProcessRunner:
        # Return a runner whose service declares only an image.
        scripted: ScriptedProcessRunner = ScriptedProcessRunner(catalogue)
        scripted.configuration = {"services": {"workspace": {"image": "sandbox/contract:latest"}}}
        return scripted

    # Supply the scripted builder.
    @pytest.fixture
    def builder(self, runner: ScriptedProcessRunner) -> DockerBuilder:
        # Return the builder under test.
        return DockerBuilder(DockerCli(runner))

    # Supply the scripted catalogue plan.
    @pytest.fixture
    def plan(self) -> SandboxPlan:
        # Return a volume-less plan.
        return make_plan(directory = Path("/work/demo"))

    # Supply the scripted recipe definition.
    @pytest.fixture
    def definition(self, catalogue: Path) -> RecipeDefinition:
        # Return the standard recipe source.
        return RecipeDefinition(
            catalogue = "default",
            recipe = "base",
            catalogue_root = catalogue,
            files = (catalogue / "compose.yaml",),
            service = "workspace",
        )

    # Supply the matching local-image requirement.
    @pytest.fixture
    def requirement(self) -> ArtifactRequirement:
        # Return the local-image requirement.
        return ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    # Select an image-only service.
    @pytest.fixture
    def buildable(self) -> bool:
        # Report an image-only service.
        return False


# Verify build, pull, and reuse semantics for focused scenarios.
def test_buildable_service_reuses_a_present_image_without_rebuilding(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Build the image once.
    first: BuildArtifact = builder.prepare(plan, definition, requirement)

    # Forget the preparation commands and reuse the image.
    runner.commands.clear()
    sink: RecordingOutputSink = RecordingOutputSink()
    second: BuildArtifact = builder.prepare(plan, definition, requirement, output = sink)

    # Require reuse without a build command or phase.
    assert first.created is True
    assert second.created is False
    assert not any("build" in command.arguments and command.arguments[:2] == ("docker", "compose") for command in runner.commands)
    assert sink.progress_phases == ()


# Verify an image-only service pulls only when the image is missing.
def test_image_only_service_pulls_only_when_missing(
    runner: ScriptedProcessRunner,
    builder: DockerBuilder,
    plan: SandboxPlan,
    definition: RecipeDefinition,
) -> None:
    # Replace the buildable service with an image-only service.
    runner.configuration = {"services": {"workspace": {"image": "sandbox/pull:latest"}}}
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/pull:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    # Pull the missing image.
    first: BuildArtifact = builder.prepare(plan, definition, requirement)

    # Require a pull without Buildx or Compose build.
    assert first.created is True
    assert any(command.arguments[:2] == ("docker", "pull") for command in runner.commands)
    assert not any(command.arguments[:3] == ("docker", "buildx", "version") for command in runner.commands)
    assert not any(command.arguments[:2] == ("docker", "compose") and "build" in command.arguments for command in runner.commands)

    # Reuse the present image even when a rebuild is requested.
    runner.commands.clear()
    second: BuildArtifact = builder.prepare(plan, definition, requirement, rebuild = True)

    # Require no second pull.
    assert second.created is False
    assert not any(command.arguments[:2] == ("docker", "pull") for command in runner.commands)


# Verify a build streams child output and announces the build phase.
def test_build_streams_output_and_announces_the_build_phase(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Prepare the image with a recording sink.
    sink: RecordingOutputSink = RecordingOutputSink()
    builder.prepare(plan, definition, requirement, output = sink)

    # Require the build phase with the selected service and the raw child chunk.
    assert sink.progress_phases == (ProgressPhase.BUILD_IMAGE,)
    assert sink.progress_subjects == ("workspace",)
    assert sink.output_bytes(OutputChannel.STDERR) == b"build output\n"

    # Require the streaming build to be uncaptured while resolution stays captured.
    build: RecordedCommand = next(command for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "build" in command.arguments)
    config: RecordedCommand = next(command for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "config" in command.arguments)
    assert build.capture is False
    assert config.capture is True


# Verify the Compose build preserves the dependency graph and plain progress.
def test_build_uses_the_dependency_graph_and_plain_progress(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Build the image.
    builder.prepare(plan, definition, requirement)

    # Read the build command.
    command: tuple[str, ...] = next(command.arguments for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "build" in command.arguments)

    # Require the selected service and its dependencies, with plain progress.
    assert command[-3:] == ("build", "--with-dependencies", "workspace")
    assert "--progress" in command and command[command.index("--progress") + 1] == "plain"


# Verify a failed build preserves the bounded command facts.
def test_build_failure_preserves_command_facts(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script a failed build with a bounded diagnostic.
    runner.build_returncode = 17
    runner.build_stderr = b"first line\nfinal build failure\n"

    # Require the typed build failure.
    with pytest.raises(BuildFailed) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the positive status, bounded diagnostic, and build command.
    failure = raised.value.failure
    assert failure.backend == "docker"
    assert failure.operation == "build"
    assert failure.exit_code == 17
    assert failure.diagnostic == "final build failure"
    assert failure.command is not None and "build" in failure.command
    assert len(failure.diagnostic) <= DIAGNOSTIC_LIMIT


# Verify a failed pull is a typed engine failure.
def test_pull_failure_is_a_typed_engine_failure(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
) -> None:
    # Script an image-only service with a failed pull.
    runner.configuration = {"services": {"workspace": {"image": "sandbox/pull:latest"}}}
    runner.pull_returncode = 125
    runner.pull_stderr = b"pull failed\n"
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/pull:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    # Require the typed engine failure.
    with pytest.raises(EngineFailure) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the pull facts and preserved status.
    assert raised.value.failure.operation == "pull"
    assert raised.value.failure.exit_code == 125
    assert raised.value.failure.diagnostic == "pull failed"


# Verify the Compose version floor fails before configuration resolution.
def test_compose_version_floor_fails_before_configuration(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script an unsupported Compose version.
    runner.compose_version = b"5.5.9\n"

    # Require the typed unsupported-version failure.
    with pytest.raises(PrerequisiteError) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the structured version facts and no configuration attempt.
    assert raised.value.tool == "docker compose"
    assert raised.value.kind is PrerequisiteKind.VERSION
    assert raised.value.found == "5.5.9"
    assert not any("config" in command.arguments for command in runner.commands)


# Verify a missing Compose plugin is a missing prerequisite.
def test_missing_compose_plugin_is_a_prerequisite(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script Docker's missing-plugin diagnostic.
    runner.compose_returncode = 1
    runner.compose_stderr = b"docker: 'compose' is not a docker command.\n"

    # Require the typed missing prerequisite.
    with pytest.raises(PrerequisiteError) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the missing-plugin classification.
    assert raised.value.tool == "docker compose"
    assert raised.value.kind is PrerequisiteKind.MISSING
    assert not any("config" in command.arguments for command in runner.commands)


# Verify the Buildx floor applies only when a build runs.
def test_buildx_is_required_only_for_a_build(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script an unsupported Buildx version.
    runner.buildx_version = b"github.com/docker/buildx v0.16.0 abcdef\n"

    # Require the typed unsupported-version failure before the build.
    with pytest.raises(PrerequisiteError) as raised:
        # Prepare the buildable image.
        builder.prepare(plan, definition, requirement)

    # Require the Buildx facts.
    assert raised.value.tool == "buildx"
    assert raised.value.kind is PrerequisiteKind.VERSION
    assert not any(command.arguments[:2] == ("docker", "compose") and "build" in command.arguments for command in runner.commands)

    # An image-only service does not probe Buildx.
    fresh: ScriptedProcessRunner = ScriptedProcessRunner(runner.catalogue)
    fresh.configuration = {"services": {"workspace": {"image": "sandbox/pull:latest"}}}
    fresh.buildx_version = b"github.com/docker/buildx v0.16.0 abcdef\n"
    artifact: BuildArtifact = DockerBuilder(DockerCli(fresh)).prepare(
        plan,
        definition,
        ArtifactRequirement(reference = "sandbox/pull:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE),
    )
    assert artifact.created is True
    assert not any(command.arguments[:3] == ("docker", "buildx", "version") for command in fresh.commands)


# Verify build contexts must stay inside the catalogue.
def test_build_context_containment_is_enforced(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script a build context outside the catalogue.
    runner.configuration["services"]["workspace"]["build"] = {"context": "/outside/context"}

    # Require the typed configuration failure.
    with pytest.raises(ConfigurationError) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the field path and no image preparation.
    assert raised.value.field == "services.workspace.build.context"
    assert not any(command.arguments[:2] == ("docker", "pull") for command in runner.commands)


# Verify Dockerfiles must stay inside the catalogue.
def test_dockerfile_containment_is_enforced(
    builder: DockerBuilder,
    catalogue: Path,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Create a Dockerfile outside the catalogue.
    outside: Path = catalogue.parent / "outside-Dockerfile"
    outside.write_text("FROM scratch\n", encoding = "utf-8")

    # Script the escaping Dockerfile.
    runner.configuration["services"]["workspace"]["build"] = {
        "context": str(catalogue / "context"),
        "dockerfile": str(outside),
    }

    # Require the typed configuration failure.
    with pytest.raises(ConfigurationError) as raised:
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require the Dockerfile field attribution.
    assert raised.value.field == "services.workspace.build.dockerfile"


# Verify valueless build arguments in both resolved forms are rejected.
@pytest.mark.parametrize("args", [["UNSET_ARG"], {"UNSET_ARG": None}])
def test_valueless_build_args_are_rejected(
    args: object,
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script the valueless arguments.
    runner.configuration["services"]["workspace"]["build"] = {
        "context": str(runner.catalogue / "context"),
        "args": args,
    }

    # Require the typed configuration failure before the image exists.
    with pytest.raises(ConfigurationError):
        # Prepare the image.
        builder.prepare(plan, definition, requirement)


# Verify an archive contains one uncompressed target image.
def test_archive_export_contains_one_target_image(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    tmp_path: Path,
) -> None:
    # Script an ARM64 image and requirement.
    runner.architecture = "arm64"
    runner.configuration["services"]["workspace"]["platform"] = "linux/arm64"
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = "linux/arm64", transport = ArtifactTransport.DOCKER_ARCHIVE)

    # Export the archive into operation-scoped staging.
    artifact: BuildArtifact = builder.prepare(plan, definition, requirement, staging_dir = tmp_path)

    # Require the artifact facts.
    assert artifact.reference == requirement.reference
    assert artifact.platform == "linux/arm64"
    assert artifact.transport is ArtifactTransport.DOCKER_ARCHIVE
    assert artifact.archive_path == tmp_path / "artifact.tar"
    assert artifact.created is True
    assert artifact.digest is None

    # Require exactly one target image in the save command.
    save: tuple[str, ...] = next(command.arguments for command in runner.commands if command.arguments[:3] == ("docker", "image", "save"))
    assert save.index("--platform") < save.index("--output")
    assert save[save.index("--platform") + 1] == "linux/arm64"
    assert save[-1] == "sandbox/contract:latest"
    assert save.count("sandbox/contract:latest") == 1

    # Require an uncompressed tar with exactly one manifest entry.
    with tarfile.open(artifact.archive_path, mode = "r:") as archive:
        manifest_file = archive.extractfile("manifest.json")
        assert manifest_file is not None
        manifest: list[dict[str, Any]] = json.load(manifest_file)

    assert len(manifest) == 1
    assert manifest[0]["RepoTags"] == ["sandbox/contract:latest"]

    # Require the transient export directory to be cleaned up.
    assert sorted(path.name for path in tmp_path.iterdir()) == ["artifact.tar"]


# Verify a mismatched architecture fails before export.
def test_archive_rejects_a_mismatched_architecture_before_export(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    tmp_path: Path,
) -> None:
    # Script an AMD64 image for an ARM64 requirement and matching service platform.
    runner.architecture = "amd64"
    runner.configuration["services"]["workspace"]["platform"] = "linux/arm64"
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = "linux/arm64", transport = ArtifactTransport.DOCKER_ARCHIVE)

    # Require the typed artifact rejection.
    with pytest.raises(ArtifactRejected) as raised:
        # Prepare the archive.
        builder.prepare(plan, definition, requirement, staging_dir = tmp_path)

    # Require the platform facts and no export command.
    assert raised.value.expected_platform == "linux/arm64"
    assert raised.value.actual_platform == "linux/amd64"
    assert not any(command.arguments[:3] == ("docker", "image", "save") for command in runner.commands)
    assert list(tmp_path.iterdir()) == []


# Verify an archive reuses a present image but still exports.
def test_archive_reuses_the_image_but_still_exports(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    tmp_path: Path,
) -> None:
    # Script an archive requirement.
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)

    # Build and export once, then export the reusable image again.
    first: BuildArtifact = builder.prepare(plan, definition, requirement, staging_dir = tmp_path)
    second: BuildArtifact = builder.prepare(plan, definition, requirement, staging_dir = tmp_path)

    # Require created to describe build/pull rather than export.
    assert first.created is True
    assert second.created is False
    assert second.archive_path is not None and second.archive_path.is_file()

    # Require two exports with no second build.
    assert sum(1 for command in runner.commands if command.arguments[:3] == ("docker", "image", "save")) == 2
    assert sum(1 for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "build" in command.arguments) == 1


# Verify OCI archives fail before any engine command.
def test_oci_archive_is_rejected_before_any_engine_command(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
) -> None:
    # Require an unimplemented OCI archive.
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.OCI_ARCHIVE)

    # Require the typed rejection without a probe.
    with pytest.raises(ArtifactRejected):
        # Prepare the archive.
        builder.prepare(plan, definition, requirement)

    # Require no engine command and no build phase.
    assert runner.commands == []


# Verify archive transports require an existing operation-scoped staging directory.
def test_archive_requires_existing_staging(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    tmp_path: Path,
) -> None:
    # Require a Docker archive.
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)

    # Require a staging directory before preparation.
    with pytest.raises(ValueError):
        # Prepare without staging.
        builder.prepare(plan, definition, requirement)

    # Require an existing staging directory.
    with pytest.raises(ValueError):
        # Prepare with a missing staging path.
        builder.prepare(plan, definition, requirement, staging_dir = tmp_path / "missing")

    # Require no engine command in either case.
    assert runner.commands == []


# Verify the manifest digest never falls back to Docker's config ID.
def test_manifest_digest_never_uses_the_config_id(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script a distinct repository digest and config ID.
    runner.config_id = "sha256:config-id"
    runner.repo_digest = "sha256:manifest-digest"

    # Prepare the local image.
    artifact: BuildArtifact = builder.prepare(plan, definition, requirement)

    # Require the repository manifest digest.
    assert artifact.digest == "sha256:manifest-digest"
    assert artifact.digest != "sha256:config-id"


# Verify the builder scopes the Compose environment per command.
def test_compose_environment_is_scoped_to_the_invocation(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure no ambient project value influences the assertion.
    monkeypatch.delenv("SB_PROJECT_NAME", raising = False)

    # Prepare the image.
    builder.prepare(plan, definition, requirement)

    # Require the project environment on every Compose command.
    config: RecordedCommand = next(command for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "config" in command.arguments)
    assert config.environment is not None
    assert config.environment["SB_PROJECT_NAME"] == "demo"
    assert config.environment["SB_PROJECT_DIRECTORY"] == "/work/demo"
    assert config.environment["COMPOSE_PROJECT_NAME"] == "demo"
    assert config.environment["DOCKER_CLI_HINTS"] == "false"

    # Require no process-wide mutation.
    assert "SB_PROJECT_NAME" not in os.environ


# Verify a required platform is applied to Compose when the service is silent.
def test_required_platform_is_applied_to_compose(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
) -> None:
    # Require an ARM64 local image with no service platform.
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = "linux/arm64", transport = ArtifactTransport.LOCAL_IMAGE)

    # Prepare the image.
    artifact: BuildArtifact = builder.prepare(plan, definition, requirement)

    # Require the platform on the artifact and in the child environment.
    assert artifact.platform == "linux/arm64"
    config: RecordedCommand = next(command for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "config" in command.arguments)
    assert config.environment is not None
    assert config.environment["DOCKER_DEFAULT_PLATFORM"] == "linux/arm64"


# Verify a resolved service image must match the runtime requirement.
def test_resolved_reference_mismatch_is_rejected(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script a different service image.
    runner.configuration["services"]["workspace"]["image"] = "sandbox/other:latest"

    # Require the artifact rejection before image inspection.
    with pytest.raises(ArtifactRejected):
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require no local image probe.
    assert not any(command.arguments[:3] == ("docker", "image", "inspect") for command in runner.commands)


# Verify a mismatched resolved service platform is rejected.
def test_resolved_platform_mismatch_is_rejected(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
) -> None:
    # Script an AMD64 service for an ARM64 requirement.
    runner.configuration["services"]["workspace"]["platform"] = "linux/amd64"
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = "linux/arm64", transport = ArtifactTransport.LOCAL_IMAGE)

    # Require the artifact rejection before preparation.
    with pytest.raises(ArtifactRejected):
        # Prepare the image.
        builder.prepare(plan, definition, requirement)

    # Require no image inspection.
    assert not any(command.arguments[:3] == ("docker", "image", "inspect") for command in runner.commands)


# Verify a multi-image archive is rejected.
def test_archive_with_multiple_images_is_rejected(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    tmp_path: Path,
) -> None:
    # Script a two-image archive produced by an invalid export.
    runner.save_images = 2
    requirement: ArtifactRequirement = ArtifactRequirement(reference = "sandbox/contract:latest", platform = None, transport = ArtifactTransport.DOCKER_ARCHIVE)

    # Require the typed rejection after the export.
    with pytest.raises(ArtifactRejected):
        # Prepare the archive.
        builder.prepare(plan, definition, requirement, staging_dir = tmp_path)

    # Require no published archive and no transient export directory.
    assert list(tmp_path.iterdir()) == []


# Verify a Compose service additional context is preserved for the build graph.
def test_service_additional_context_is_preserved(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script the service-based additional context in the resolved array form.
    runner.configuration["services"]["workspace"]["build"]["additional_contexts"] = ["base=service:base"]

    # Build the service with its dependency.
    artifact: BuildArtifact = builder.prepare(plan, definition, requirement)

    # Require a successful build and the dependency graph flag.
    assert artifact.created is True
    command: tuple[str, ...] = next(command.arguments for command in runner.commands if command.arguments[:2] == ("docker", "compose") and "build" in command.arguments)
    assert command[-3:] == ("build", "--with-dependencies", "workspace")


# Verify a remote additional build context is rejected.
def test_remote_additional_context_is_rejected(
    builder: DockerBuilder,
    runner: ScriptedProcessRunner,
    plan: SandboxPlan,
    definition: RecipeDefinition,
    requirement: ArtifactRequirement,
) -> None:
    # Script a remote additional context.
    runner.configuration["services"]["workspace"]["build"]["additional_contexts"] = {"base": "https://example.invalid/context.git"}

    # Require the typed configuration failure.
    with pytest.raises(ConfigurationError):
        # Prepare the image.
        builder.prepare(plan, definition, requirement)
