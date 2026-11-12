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


# Build one home-scoped SDK client per requested configuration home.
class SandboxClientFactory:
    # Bind the factory to its adapters and advisory output sink.
    def __init__(
        self,
        *,
        output: OutputSink = SILENT,
        integrations: ClientAdapters | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        # Require a usable output sink.
        if not isinstance(output, OutputSink):
            # Throw a programming error for Python API misuse.
            raise TypeError("output must implement the OutputSink port.")

        # Validate an explicitly supplied adapter bundle.
        if integrations is not None:
            # Require both neutral ports together.
            if not isinstance(getattr(integrations, "builder", None), Builder) or not isinstance(getattr(integrations, "runtime", None), Runtime):
                # Throw a programming error for an incomplete bundle.
                raise ValueError("integrations must supply both a builder and a runtime.")

        # Retain the injected values without constructing an adapter.
        self._output: OutputSink = output
        self._integrations: ClientAdapters | None = integrations
        self._runner: CommandRunner | None = runner

    # Read the advisory sink used by clients that do not override it.
    @property
    def output(self) -> OutputSink:
        # Return the injected sink.
        return self._output

    # Read the adapters, building the production Docker set on first use.
    @property
    def integrations(self) -> ClientAdapters:
        # Build the Docker adapters lazily so help, version, and completion stay inert.
        adapters: ClientAdapters | None = self._integrations
        if adapters is None:
            # Construct the shared Docker gateway and its two adapters.
            adapters = build_docker_integrations(self._runner)
            self._integrations = adapters

        # Return the retained or freshly built adapters.
        return adapters

    # Build a client bound to one configuration home and output sink.
    def for_home(self, home: Path, *, output: OutputSink = SILENT) -> SandboxClient:
        # Prefer a per-client override and fall back to the injected default.
        sink: OutputSink = self._output if output is SILENT else output

        # Require a usable sink before constructing the client.
        if not isinstance(sink, OutputSink):
            # Throw a programming error for Python API misuse.
            raise TypeError("output must implement the OutputSink port.")

        # Read the adapters once so every client shares the same wiring.
        adapters: ClientAdapters = self.integrations

        # Build the inert home-scoped client.
        return SandboxClient(
            home = home,
            runtime = adapters.runtime,
            builder = adapters.builder,
            output = sink,
        )
