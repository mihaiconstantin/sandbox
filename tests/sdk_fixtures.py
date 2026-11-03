"""Provide temporary configuration homes, catalogues, and fake-port clients for SDK tests."""

# Imports.
from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

# Import domain values.
from sandbox.domain.artifact import ArtifactRequirement, ArtifactTransport, BuildArtifact
from sandbox.domain.mount import MountSpec
from sandbox.domain.observation import BoxObservation, BoxState, Provenance, RuntimeRef
from sandbox.domain.paths import project_target
from sandbox.domain.plan import RecipeDefinition, SandboxPlan
from sandbox.domain.requirements import RuntimeRequirements, SandboxSpec
from sandbox.domain.volume import VolumeDeclaration

# Import the SDK client.
from sandbox.sdk import SandboxClient

# Import the shipped fakes.
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.output import RecordingOutputSink
from sandbox.testing.runtime import FakeRuntime

# Import the silent output default.
from sandbox.ports.output import SILENT, OutputSink


# Adapt a test callable to the CLI client factory protocol.
class FunctionClientFactory:
    # Retain the callable.
    def __init__(self, factory: Any) -> None:
        # Store the callable.
        self._factory: Any = factory

    # Build a client for one home and optional output sink.
    def for_home(self, home: Path, *, output: OutputSink = SILENT) -> SandboxClient:
        # Delegate directly to an object that already implements the protocol.
        if hasattr(self._factory, "for_home"):
            return self._factory.for_home(home, output = output)

        # Prefer the output-aware signature and fall back to the home-only signature.
        try:
            return self._factory(home, output = output)
        except TypeError:
            return self._factory(home)

# Declare the fixed image used by fake runtimes.
FAKE_IMAGE: str = "sandbox/demo:latest"

# Declare the catalogue manifest body with optional volume and secret declarations.
MANIFEST: str = dedent("""\
    [catalogue]
    name = "{name}"
    version = "0.1.0"
    schema_version = 1
    default_recipe = "base"

    {declarations}
    [recipes.base]
    compose = "compose.yaml"
    service = "workspace"
    {requirements}
""")


# Build a catalogue manifest for the requested declarations.
def manifest_for(name: str, *, volume: bool, secret: bool) -> str:
    # Build the declared volume and secret blocks.
    declarations: list[str] = []
    requirements: list[str] = []

    # Add a shared volume declaration when requested.
    if volume:
        declarations.append(
            dedent("""\
                [volumes.state]
                name = "example-state"
                scope = "shared"
                target = "/home/example/.state"
            """)
        )
        requirements.append('volumes = ["state"]')

    # Add a secret requirement when requested.
    if secret:
        requirements.append('secrets = ["example-secret"]')

    # Join the optional declaration and requirement lines.
    return MANIFEST.format(
        name = name,
        declarations = "\n".join(declarations),
        requirements = "\n    ".join(requirements),
    )


# Create a registered catalogue directory with a manifest and compose file.
def write_catalogue(
    home: Path,
    name: str = "default",
    *,
    volume: bool = True,
    secret: bool = False,
    register: bool = True,
) -> Path:
    # Create the canonical catalogue directory.
    directory: Path = home / "catalogues" / name
    directory.mkdir(parents = True)

    # Write the manifest and its declared compose file.
    (directory / "catalogue.toml").write_text(manifest_for(name, volume = volume, secret = secret), encoding = "utf-8")
    (directory / "compose.yaml").write_text("services: {}\n", encoding = "utf-8")

    # Register the catalogue when requested.
    if register:
        registry: Path = home / "catalogues.toml"
        registry.write_text(
            f'[catalogues.{name}]\ntype = "bundled"\npath = "catalogues/{name}"\n',
            encoding = "utf-8",
        )

    # Return the catalogue directory.
    return directory


# Create a readable host secret file and bind it to the catalogue.
def bind_secret(home: Path, catalogue: str = "default", alias: str = "example-secret") -> Path:
    # Create the secret file.
    path: Path = home / "keys" / alias
    path.parent.mkdir(parents = True)
    path.write_text("not displayed\n", encoding = "utf-8")

    # Bind the secret through the real configuration store.
    from sandbox.configuration.store import ConfigurationStore

    ConfigurationStore(home).save_secret(catalogue, alias, path)
    return path


# Build a client over one temporary home and the shipped fake ports.
def make_client(
    home: Path,
    *,
    runtime: FakeRuntime | None = None,
    builder: FakeBuilder | None = None,
    output: RecordingOutputSink | None = None,
) -> SandboxClient:
    # Construct the public client with explicit fakes.
    return SandboxClient(
        home = home,
        runtime = runtime if runtime is not None else FakeRuntime(),
        builder = builder if builder is not None else FakeBuilder(),
        output = output,
    )


# Build a plausible observed box for lifecycle tests.
def make_observation(name: str = "demo", state: BoxState = BoxState.RUNNING) -> BoxObservation:
    # Return the fixed observation.
    return BoxObservation(
        name = name,
        state = state,
        provenance = Provenance(catalogue = "default", recipe = "base"),
        status_text = state.value,
        image = FAKE_IMAGE,
        working_directory = project_target(name),
        backend = RuntimeRef(id = f"fake-{name}", name = name),
    )


# Build runtime requirements for the requested project and transport.
def make_requirements(
    project: str,
    project_dir: Path,
    *,
    volumes: tuple[VolumeDeclaration, ...] = (),
    transport: ArtifactTransport = ArtifactTransport.LOCAL_IMAGE,
    platform: str | None = None,
) -> RuntimeRequirements:
    # Build the neutral mounts from the workspace and declared volumes.
    mounts: tuple[MountSpec, ...] = (
        MountSpec(kind = "bind", source = project_dir, target = project_target(project), read_only = False),
        *(MountSpec(kind = "volume", source = volume.name, target = volume.target, read_only = False) for volume in volumes),
    )

    # Build the effective sandbox spec.
    spec: SandboxSpec = SandboxSpec(
        image = FAKE_IMAGE,
        platform = platform,
        user = None,
        working_directory = project_target(project),
        privileged = False,
        host_network = False,
        mounts = mounts,
    )

    # Build the required artifact facts.
    artifact: ArtifactRequirement = ArtifactRequirement(
        reference = FAKE_IMAGE,
        platform = platform,
        transport = transport,
    )

    # Return the neutral requirements.
    return RuntimeRequirements(spec = spec, artifact = artifact)


# Record port calls in one ordered event log for create-order tests.
class RecordingRuntime(FakeRuntime):
    # Construct the fake runtime and retain the shared log.
    def __init__(self, events: list[str], **configuration: Any) -> None:
        # Initialize the stateful fake.
        super().__init__(**configuration)
        self.events: list[str] = events

    # Record runtime preparation.
    def prepare(self, plan: SandboxPlan, definition: RecipeDefinition):
        # Record the call before delegating.
        self.events.append("runtime.prepare")
        return super().prepare(plan, definition)

    # Record initialization planning.
    def plan_initialization(self, preparation, artifact: BuildArtifact):
        # Record the call before delegating.
        self.events.append("runtime.plan_initialization")
        return super().plan_initialization(preparation, artifact)

    # Record box creation.
    def create(self, preparation, artifact: BuildArtifact, initialization = None, *, output = None):
        # Record the call before delegating.
        self.events.append("runtime.create")
        return super().create(preparation, artifact, initialization, output = output)

    # Record volume ensure calls.
    def ensure_volume(self, name: str):
        # Record the call before delegating.
        self.events.append(f"runtime.ensure_volume:{name}")
        return super().ensure_volume(name)


# Record builder preparation in the shared event log.
class RecordingBuilder(FakeBuilder):
    # Construct the fake builder and retain the shared log.
    def __init__(self, events: list[str], **configuration: Any) -> None:
        # Initialize the stateful fake.
        super().__init__(**configuration)
        self.events: list[str] = events

    # Record image preparation.
    def prepare(self, plan: SandboxPlan, definition: RecipeDefinition, requirement: ArtifactRequirement, **options: Any) -> BuildArtifact:
        # Record the call before delegating.
        self.events.append("builder.prepare")
        return super().prepare(plan, definition, requirement, **options)
