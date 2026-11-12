"""Verify the production composition root builds one inert, home-scoped client wiring."""

# Imports.
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

# Import the CLI factory contract.
from sandbox.cli.context import ClientFactory

# Import the composition root and adapter selection.
from sandbox.composition.client import ClientAdapters, SandboxClientFactory
from sandbox.composition.integrations import DockerIntegrations, build_docker_integrations

# Import the concrete integrations.
from sandbox.integrations.docker.builder import DockerBuilder
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.compose.runtime import ComposeRuntime

# Import the neutral port values.
from sandbox.ports.output import ProgressPhase

# Import the shipped fakes.
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.output import RecordingOutputSink
from sandbox.testing.runtime import FakeRuntime


# Verify the factory satisfies the protocol the CLI consumes.
def test_factory_satisfies_the_cli_contract() -> None:
    # Compare the runtime-checkable protocol.
    assert isinstance(SandboxClientFactory(), ClientFactory)


# Verify adapter selection holds one Docker CLI behind two distinct adapters.
def test_integrations_share_one_docker_cli_and_separate_builder_and_runtime() -> None:
    # Build the production integration bundle.
    integrations: DockerIntegrations = build_docker_integrations()

    # Require the distinct adapter types around one gateway.
    assert isinstance(integrations.docker, DockerCli)
    assert isinstance(integrations.builder, DockerBuilder)
    assert isinstance(integrations.runtime, ComposeRuntime)
    assert integrations.builder is not integrations.runtime
    assert integrations.builder._docker is integrations.docker
    assert integrations.runtime._docker is integrations.docker


# Verify the default factory builds the Docker adapters lazily.
def test_factory_builds_docker_adapters_only_when_a_client_is_requested() -> None:
    # Construct a factory without touching any adapter.
    factory: SandboxClientFactory = SandboxClientFactory()

    # Require the adapters only on first use.
    assert isinstance(factory.integrations, DockerIntegrations)
    assert isinstance(factory.integrations.builder, DockerBuilder)
    assert isinstance(factory.integrations.runtime, ComposeRuntime)


# Verify each requested home receives its own inert client.
def test_factory_builds_one_client_per_home_without_reading_it(tmp_path: Path) -> None:
    # Construct one factory and request two homes.
    factory: SandboxClientFactory = SandboxClientFactory()
    first_home: Path = tmp_path / "first"
    second_home: Path = tmp_path / "second"

    # Build one client per home.
    first = factory.for_home(first_home)
    second = factory.for_home(second_home)

    # Require home binding, independent clients, and no directory creation.
    assert first.home == first_home
    assert second.home == second_home
    assert first is not second
    assert not first_home.exists()
    assert not second_home.exists()


# Verify the injected output sink reaches SDK operations.
def test_factory_injects_output_into_the_client(tmp_path: Path) -> None:
    # Construct a factory with fake adapters and a recording sink.
    sink: RecordingOutputSink = RecordingOutputSink()
    adapters = cast(ClientAdapters, cast(object, SimpleNamespace(builder = FakeBuilder(), runtime = FakeRuntime())))
    factory: SandboxClientFactory = SandboxClientFactory(integrations = adapters, output = sink)

    # Run one SDK operation that reports progress.
    client = factory.for_home(tmp_path)
    client.volumes.ensure("shared-state")

    # Require the injected sink to receive the operation progress.
    assert factory.output is sink
    assert sink.progress_phases == (ProgressPhase.ENSURE_VOLUME,)
    assert sink.progress_subjects == ("shared-state",)


# Verify a caller-supplied sink overrides the factory default for one client.
def test_factory_honors_a_per_client_output_override(tmp_path: Path) -> None:
    # Construct a factory with a recording default and a second explicit sink.
    default_sink: RecordingOutputSink = RecordingOutputSink()
    override: RecordingOutputSink = RecordingOutputSink()
    adapters = cast(ClientAdapters, cast(object, SimpleNamespace(builder = FakeBuilder(), runtime = FakeRuntime())))
    factory: SandboxClientFactory = SandboxClientFactory(integrations = adapters, output = default_sink)

    # Run the client with the explicit sink.
    factory.for_home(tmp_path, output = override).volumes.ensure("override-state")

    # Require the override and leave the default untouched.
    assert override.progress_phases == (ProgressPhase.ENSURE_VOLUME,)
    assert default_sink.progress_phases == ()


# Verify an incomplete adapter injection is rejected before use.
def test_factory_rejects_an_incomplete_adapter_bundle() -> None:
    # Require both neutral ports together.
    with pytest.raises(ValueError):
        SandboxClientFactory(integrations = cast(ClientAdapters, cast(object, SimpleNamespace(builder = FakeBuilder(), runtime = None))))
