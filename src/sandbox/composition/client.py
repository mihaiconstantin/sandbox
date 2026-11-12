# Imports.
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

# Import the neutral ports and output values.
from sandbox.ports.builder import Builder
from sandbox.ports.output import SILENT, OutputSink
from sandbox.ports.runtime import Runtime

# Import the process seam.
from sandbox.integrations.docker.command import CommandRunner

# Import the Docker adapter selection.
from sandbox.composition.integrations import build_docker_integrations

# Import the public SDK client.
from sandbox.sdk import SandboxClient


# Represent the two neutral ports a client factory needs.
@runtime_checkable
class ClientAdapters(Protocol):
    # Hold the image builder.
    @property
    def builder(self) -> Builder: ...

    # Hold the runtime.
    @property
    def runtime(self) -> Runtime: ...
