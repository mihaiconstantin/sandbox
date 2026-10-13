"""Verify the repository-only microsandbox-shaped runtime fake against the port contract."""

# Imports.
from collections.abc import Callable
from pathlib import Path

# Import pytest for fixtures and typed error assertions.
import pytest

# Import the shared runtime contract and neutral fixtures.
from port_contract import RuntimeContract, build_matching_artifact
from neutral_fixtures import make_definition, make_plan

# Import neutral domain values.
from sandbox.domain import ArtifactTransport, BuildArtifact, Secret
from sandbox.errors.capabilities import ArtifactRejected

# Import the repository-only fake.
from microsandbox_fake import MicrosandboxPreparation, MicrosandboxShapedRuntime


# Verify the microsandbox-shaped fake satisfies the Runtime contract.
class TestMicrosandboxRuntimeContract(RuntimeContract):
    # Supply a fresh fake runtime.
    @pytest.fixture
    def runtime(self) -> MicrosandboxShapedRuntime:
        # Return a default microsandbox-shaped runtime.
        return MicrosandboxShapedRuntime()

    # Supply a second independent fake runtime.
    @pytest.fixture
    def other_runtime(self) -> MicrosandboxShapedRuntime:
        # Return another independent runtime.
        return MicrosandboxShapedRuntime()

    # Supply a runtime configured for one interactive shell status.
    @pytest.fixture
    def runtime_with_enter_status(self) -> Callable[[int], MicrosandboxShapedRuntime]:
        # Return a factory that records the requested shell status.
        return lambda status: MicrosandboxShapedRuntime(enter_status = status)


# Verify the fake requires an archive artifact with readable bytes before mutation.
def test_archive_artifact_is_required_before_mutation(tmp_path: Path) -> None:
    # Prepare a runtime and a plan.
    runtime: MicrosandboxShapedRuntime = MicrosandboxShapedRuntime()
    plan = make_plan()
    preparation = runtime.prepare(plan, make_definition())

    # Require an archive transport.
    assert preparation.requirements.artifact.transport is ArtifactTransport.DOCKER_ARCHIVE

    # Build an artifact whose archive does not exist.
    artifact: BuildArtifact = BuildArtifact(
        reference = preparation.requirements.artifact.reference,
        platform = None,
        digest = None,
        transport = ArtifactTransport.DOCKER_ARCHIVE,
        archive_path = tmp_path / "missing.tar",
        created = False,
    )

    # Require the pre-load archive check before mutation.
    with pytest.raises(ArtifactRejected):
        runtime.create(preparation, artifact)
    assert runtime.inspect(plan.project.name) is None


# Verify secret files are delivered read-only and separate from storage mounts.
def test_secret_files_are_read_only_deliveries(tmp_path: Path) -> None:
    # Prepare one readable secret file.
    secret_file: Path = tmp_path / "token"
    secret_file.write_text("secret\n", encoding = "utf-8")

    # Prepare the plan with one secret binding.
    plan = make_plan(secrets = (Secret(alias = "token", host_path = secret_file),))
    runtime: MicrosandboxShapedRuntime = MicrosandboxShapedRuntime()
    preparation: MicrosandboxPreparation = runtime.prepare(plan, make_definition())

    # Require a read-only secret delivery outside the neutral storage mounts.
    assert preparation.secret_mounts[0].read_only is True
    assert preparation.secret_mounts[0].target == "/run/secrets/token"
    assert all(mount.target != "/run/secrets/token" for mount in preparation.requirements.spec.mounts)

    # Create the box and require the delivered secret mount.
    artifact: BuildArtifact = build_matching_artifact(preparation, tmp_path)
    observation = runtime.create(preparation, artifact)
    assert observation.mounts is not None
    assert any(mount.target == "/run/secrets/token" for mount in observation.mounts)


# Verify unavailable native observation facts remain `None`, not invented values.
def test_unavailable_observation_facts_remain_nullable(tmp_path: Path) -> None:
    # Create one box and one volume.
    plan = make_plan()
    runtime: MicrosandboxShapedRuntime = MicrosandboxShapedRuntime()
    preparation = runtime.prepare(plan, make_definition())
    artifact: BuildArtifact = build_matching_artifact(preparation, tmp_path)
    runtime.create(preparation, artifact)
    runtime.ensure_volume("cache")

    # Require unavailable box facts to stay `None`.
    observation = runtime.inspect(plan.project.name)
    assert observation is not None
    assert observation.status_text is None
    assert observation.working_directory is None
    assert observation.workspace is None
    assert observation.networks is None
    assert observation.backend is None

    # Require unavailable volume facts to stay `None`.
    info = runtime.inspect_volume("cache")
    assert info is not None
    assert info.driver is None
    assert info.mountpoint is None
    assert info.in_use_by is None
