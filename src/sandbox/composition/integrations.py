# Imports.
from __future__ import annotations

from dataclasses import dataclass

# Import the process seam.
from sandbox.integrations.docker.command import CommandRunner

# Import the concrete Docker integrations.
from sandbox.integrations.docker.builder import DockerBuilder
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.compose.runtime import ComposeRuntime
from sandbox.integrations.docker.runner import SubprocessRunner


# Bundle the one Docker gateway and the two independent adapters built over it.
@dataclass(frozen = True, slots = True)
class DockerIntegrations:
    # Hold the shared Docker CLI gateway.
    docker: DockerCli

    # Hold the image builder.
    builder: DockerBuilder

    # Hold the Compose runtime.
    runtime: ComposeRuntime


# Build the production Docker adapters around one shared Docker CLI.
def build_docker_integrations(runner: CommandRunner | None = None) -> DockerIntegrations:
    # Construct one gateway over the supplied or production process runner.
    docker: DockerCli = DockerCli(SubprocessRunner() if runner is None else runner)

    # Build the distinct builder and runtime over the same gateway.
    return DockerIntegrations(
        docker = docker,
        builder = DockerBuilder(docker),
        runtime = ComposeRuntime(docker),
    )


# Define the public API of the `sandbox.composition.integrations` module.
__all__: list[str] = ["DockerIntegrations", "build_docker_integrations"]
