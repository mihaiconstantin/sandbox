"""Verify shared-volume operations, validation, and output phases through the SDK."""

# Imports.
from pathlib import Path

import pytest

# Import typed errors.
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.volumes import VolumeInUse, VolumeReferencesUnavailable

# Import the output vocabulary and recording sink.
from sandbox.ports.output import ProgressPhase
from sandbox.testing.output import RecordingOutputSink
from sandbox.testing.runtime import FakeRuntime

# Import the public SDK.
from sandbox.sdk import SandboxClient
from sandbox.testing.builder import FakeBuilder

# Import the shared validation rule.
from sandbox.validation.identifiers import validate_volume_name


# Build a client over an empty fake runtime and a temporary home.
def make_runtime_client(tmp_path: Path, *, output: RecordingOutputSink | None = None) -> tuple[SandboxClient, FakeRuntime]:
    # Prepare the fake runtime and client.
    runtime: FakeRuntime = FakeRuntime()
    return SandboxClient(home = tmp_path / "home", runtime = runtime, builder = FakeBuilder(), output = output), runtime


# Verify ensure reports creation and emits the volume phase.
def test_ensure_creates_a_missing_volume(tmp_path: Path) -> None:
    # Prepare a recording sink.
    output = RecordingOutputSink()
    client, runtime = make_runtime_client(tmp_path, output = output)

    # Ensure the volume.
    ensured = client.volumes.ensure("shared")

    # Require the creation result and phase.
    assert ensured.created is True
    assert ensured.info.name == "shared"
    assert output.progress_phases == (ProgressPhase.ENSURE_VOLUME,)
    assert output.progress_subjects == ("shared",)

    # Require reuse without a second creation.
    reused = client.volumes.ensure("shared")
    assert reused.created is False
    assert runtime.list_volumes() == (ensured.info,)


# Verify get returns the observation or proven absence.
def test_get_returns_observation_and_absence(tmp_path: Path) -> None:
    # Prepare one volume.
    client, _ = make_runtime_client(tmp_path)
    ensured = client.volumes.ensure("shared")

    # Require the observation and the absence.
    assert client.volumes.get("shared") == ensured.info
    assert client.volumes.get("missing") is None


# Verify listing is sorted by physical name.
def test_list_returns_volumes_in_name_order(tmp_path: Path) -> None:
    # Seed volumes out of order directly through the runtime.
    client, runtime = make_runtime_client(tmp_path)
    for name in ("zeta", "alpha", "middle"):
        runtime.ensure_volume(name)

    # Require the sorted listing.
    assert [volume.name for volume in client.volumes.list()] == ["alpha", "middle", "zeta"]


# Verify remove applies the runtime policy and emits the phase.
def test_remove_deletes_an_unreferenced_volume(tmp_path: Path) -> None:
    # Prepare and ensure one volume.
    output = RecordingOutputSink()
    client, runtime = make_runtime_client(tmp_path, output = output)
    client.volumes.ensure("shared")

    # Remove the volume through the SDK.
    client.volumes.remove("shared")

    # Require the removal phase and absence.
    assert output.progress_phases == (ProgressPhase.ENSURE_VOLUME, ProgressPhase.REMOVE_VOLUME)
    assert runtime.inspect_volume("shared") is None


# Verify missing volumes and in-use volumes raise typed errors.
def test_remove_propagates_volume_errors(tmp_path: Path) -> None:
    # Prepare an empty runtime and seed one volume.
    client, runtime = make_runtime_client(tmp_path)
    runtime.ensure_volume("shared")
    failure = VolumeInUse("shared")
    runtime.fail_next(failure)
    with pytest.raises(VolumeInUse) as raised:
        client.volumes.remove("shared")
    assert raised.value is failure
    assert runtime.inspect_volume("shared") is not None


# Verify unavailable references cross unchanged.
def test_remove_propagates_unavailable_references(tmp_path: Path) -> None:
    # Seed one volume and queue the unavailable-reference failure.
    client, runtime = make_runtime_client(tmp_path)
    runtime.ensure_volume("shared")
    runtime.fail_next(VolumeReferencesUnavailable("shared"))

    # Require the typed failure.
    with pytest.raises(VolumeReferencesUnavailable):
        client.volumes.remove("shared")


# Verify invalid physical names are rejected before the runtime.
@pytest.mark.parametrize("name", ["", "a", "has space", "has/slash", ".leading", "-leading"])
def test_invalid_volume_names_are_rejected_before_the_runtime(tmp_path: Path, name: str) -> None:
    # Prepare an empty runtime.
    client, runtime = make_runtime_client(tmp_path)

    # Require the typed input error on every name-taking operation.
    for operation in (client.volumes.ensure, client.volumes.get, client.volumes.remove):
        with pytest.raises(ConfigurationError) as raised:
            operation(name)
        assert raised.value.field == "volume.name"

    # Require that no volume reached the runtime.
    assert runtime.ensure_volume_requests == []
    assert runtime.remove_volume_requests == []


# Verify the shared pure rule accepts Docker-compatible names and rejects others.
def test_shared_volume_name_rule() -> None:
    # Accept representative Docker volume names.
    for name in ("ab", "shared", "My.Volume-1", "a_b.c"):
        validate_volume_name(name)

    # Reject invalid names.
    for name in ("", "a", "has space", "has/slash", ".hidden", "-hidden"):
        with pytest.raises(ConfigurationError):
            validate_volume_name(name)
