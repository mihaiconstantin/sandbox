"""Exercise the real DockerBuilder and ComposeRuntime ports on an opt-in Docker host.

These tests require a Docker daemon, Compose >= 5.6.0, Buildx >= 0.17.0, network access
for the base image, and a real terminal for the interactive shell scenario. They are
skipped unless `SANDBOX_REAL_DOCKER=1`. Real-engine execution is unverified in the
development environment used for this rewrite.
"""

# Imports.
import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Import pytest for fixtures and gating.
import pytest

# Import the shared contracts.
from port_contract import BuilderContract, RuntimeContract

# Import neutral domain values.
from sandbox.domain import ArtifactRequirement, ArtifactTransport, RecipeDefinition, SandboxPlan

# Import the real integrations under test.
from sandbox.integrations.docker.builder import DockerBuilder
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.compose.runtime import ComposeRuntime
from sandbox.integrations.docker.runner import SubprocessRunner
from sandbox.ports.runtime import Runtime

# Import the neutral fixture helper.
from neutral_fixtures import make_plan

# Gate real-engine execution behind an explicit opt-in.
REAL_DOCKER: bool = os.environ.get("SANDBOX_REAL_DOCKER") == "1"
pytestmark = pytest.mark.skipif(not REAL_DOCKER, reason = "Set SANDBOX_REAL_DOCKER=1 to run real Docker contract tests.")


# Record one real catalogue, project, and its unique image reference.
@dataclass(frozen = True, slots = True)
class RealCatalogue:
    # Record the catalogue root.
    root: Path

    # Record the host project directory.
    project: Path

    # Record the unique image reference for this test.
    image: str

    # Record the opaque recipe definition.
    definition: RecipeDefinition


# Build one real catalogue with a runnable image and build context.
@pytest.fixture
def catalogue(tmp_path: Path) -> RealCatalogue:
    # Allocate a unique image reference to keep tests independent.
    image: str = f"sandbox/contract:{uuid.uuid4().hex}"

    # Create the catalogue root and build context.
    root: Path = tmp_path / "catalogue"
    context: Path = root / "context"
    context.mkdir(parents = True)

    # Write a minimal image with a non-root user and `id`.
    (context / "Dockerfile").write_text(
        "FROM alpine:3.20\nRUN adduser -D -u 1000 app\nUSER app\nWORKDIR /projects/demo\n",
        encoding = "utf-8",
    )

    # Write the buildable service definition.
    (root / "compose.yaml").write_text(
        f"services:\n  workspace:\n    image: {image}\n    build:\n      context: ./context\n      dockerfile: Dockerfile\n",
        encoding = "utf-8",
    )

    # Create the host project directory.
    project: Path = tmp_path / "project"
    project.mkdir()

    # Build the opaque recipe definition.
    definition: RecipeDefinition = RecipeDefinition(
        catalogue = "default",
        recipe = "base",
        catalogue_root = root,
        files = (root / "compose.yaml",),
        service = "workspace",
    )

    # Return the real catalogue facts.
    return RealCatalogue(root = root, project = project, image = image, definition = definition)


# Supply one real Docker gateway over the production process runner.
@pytest.fixture
def docker() -> DockerCli:
    # Return the real gateway.
    return DockerCli(SubprocessRunner())


# Build the neutral plan against the real project directory.
@pytest.fixture
def plan(catalogue: RealCatalogue) -> SandboxPlan:
    # Return a volume-less plan for the test project.
    return make_plan(directory = catalogue.project)


# Supply the real opaque recipe definition.
@pytest.fixture
def definition(catalogue: RealCatalogue) -> RecipeDefinition:
    # Return the catalogue definition.
    return catalogue.definition


# Supply the local-image requirement matching the real service.
@pytest.fixture
def requirement(catalogue: RealCatalogue) -> ArtifactRequirement:
    # Require the unique local image.
    return ArtifactRequirement(reference = catalogue.image, platform = None, transport = ArtifactTransport.LOCAL_IMAGE)


# Remove test containers, networks, and images after each scenario.
@pytest.fixture(autouse = True)
def cleanup(catalogue: RealCatalogue) -> Iterator[None]:
    # Run the scenario.
    yield

    # Remove the Compose project resources, including volumes and the image.
    subprocess.run(
        ["docker", "compose", "-p", "demo", "down", "--volumes", "--remove-orphans", "--rmi", "local"],
        cwd = catalogue.root,
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
        check = False,
    )

    # Remove the unique image when it remains.
    subprocess.run(["docker", "image", "rm", "-f", catalogue.image], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL, check = False)


# Verify the real builder satisfies the shared builder contract.
class TestRealDockerBuilderContract(BuilderContract):
    # Supply the real builder.
    @pytest.fixture
    def builder(self, docker: DockerCli) -> DockerBuilder:
        # Return the builder under test.
        return DockerBuilder(docker)

    # Supply the real project plan.
    @pytest.fixture
    def plan(self, catalogue: RealCatalogue) -> SandboxPlan:
        # Return a volume-less plan for the test project.
        return make_plan(directory = catalogue.project)

    # Supply the real recipe definition.
    @pytest.fixture
    def definition(self, catalogue: RealCatalogue) -> RecipeDefinition:
        # Return the catalogue definition.
        return catalogue.definition

    # Supply the matching local-image requirement.
    @pytest.fixture
    def requirement(self, catalogue: RealCatalogue) -> ArtifactRequirement:
        # Require the unique local image.
        return ArtifactRequirement(reference = catalogue.image, platform = None, transport = ArtifactTransport.LOCAL_IMAGE)


# Verify the real Compose runtime satisfies the shared runtime contract.
class TestRealComposeRuntimeContract(RuntimeContract):
    # Build the unique image before the runtime scenarios.
    @pytest.fixture(autouse = True)
    def prepared_image(self, catalogue: RealCatalogue) -> None:
        # Build the image from the real catalogue context.
        subprocess.run(
            ["docker", "build", "-t", catalogue.image, str(catalogue.root / "context")],
            cwd = catalogue.root,
            stdout = subprocess.DEVNULL,
            stderr = subprocess.DEVNULL,
            check = True,
        )

    # Supply the real project plan.
    @pytest.fixture
    def plan(self, catalogue: RealCatalogue) -> SandboxPlan:
        # Return a volume-less plan for the test project.
        return make_plan(directory = catalogue.project)

    # Supply the real recipe definition.
    @pytest.fixture
    def definition(self, catalogue: RealCatalogue) -> RecipeDefinition:
        # Return the catalogue definition.
        return catalogue.definition

    # Supply the real runtime over the production process runner.
    @pytest.fixture
    def runtime(self, docker: DockerCli) -> ComposeRuntime:
        # Return the runtime under test with a real terminal claim.
        return ComposeRuntime(docker, interactive_terminal = lambda: sys.stdin.isatty())

    # Supply a second independent runtime.
    @pytest.fixture
    def other_runtime(self, docker: DockerCli) -> ComposeRuntime:
        # Return another independent runtime.
        return ComposeRuntime(docker, interactive_terminal = lambda: sys.stdin.isatty())

    # Skip the scripted shell-status scenario on a real engine.
    @pytest.fixture
    def runtime_with_enter_status(self) -> Callable[[int], Runtime]:
        # A real interactive status cannot be scripted deterministically.
        pytest.skip("Real interactive shell statuses are verified manually.")
