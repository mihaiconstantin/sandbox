# Imports.
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# Import the public errors raised while resolving a Compose project.
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.cli import DockerCli

# Import the pure Compose argument builders.
from sandbox.integrations.docker.invocation import (
    compose_build_arguments,
    compose_config_arguments,
    compose_version_arguments,
)

# Import the neutral output contract.
from sandbox.ports.output import SILENT, OutputSink

# Import the opaque recipe source.
from sandbox.domain import RecipeDefinition


# Run shared read-only and streaming Compose commands.
class ComposeCli:
    # Construct the Compose gateway around the Docker gateway.
    def __init__(self, docker: DockerCli) -> None:
        # Record the shared Docker gateway.
        self._docker: DockerCli = docker

    # Read the installed Compose version without translating its status.
    def version_result(self) -> CommandResult:
        # Execute the short version probe.
        return self._docker.run(compose_version_arguments(), operation = "preflight")
