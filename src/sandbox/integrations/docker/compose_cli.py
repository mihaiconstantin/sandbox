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

    # Resolve the complete project configuration as structured JSON.
    def configuration(
        self,
        definition: RecipeDefinition,
        compose_files: Sequence[Path],
        environment: Mapping[str, str],
    ) -> Mapping[str, Any]:
        # Build the configuration command.
        arguments: list[str] = compose_config_arguments(definition, compose_files)

        # Run the read-only resolution with captured output.
        result: CommandResult = self._docker.run(arguments, operation = "resolve", environment = environment)

        # If the resolution command failed.
        if result.returncode != 0:
            # Translate the engine failure once.
            raise EngineFailure(self._docker.failure("resolve", arguments, result))

        # Parse the resolved model as strict UTF-8 JSON.
        try:
            # Parse the complete output.
            payload: Any = json.loads(result.stdout)

        # If the output is not JSON.
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            # Translate the malformed response without leaking the parser error.
            sample: str = result.stdout[:200].decode("utf-8", errors = "replace")
            raise EngineOutputInvalid("docker", "resolve", sample) from error

        # Require a top-level configuration mapping.
        if not isinstance(payload, Mapping):
            # Throw.
            raise EngineOutputInvalid("docker", "resolve", result.stdout[:200].decode("utf-8", errors = "replace"))

        # Return the resolved configuration.
        return payload

    # Build the selected service and every dependency with visible child output.
    def build(
        self,
        definition: RecipeDefinition,
        compose_files: Sequence[Path],
        service: str,
        environment: Mapping[str, str],
        output: OutputSink = SILENT,
    ) -> CommandResult:
        # Build the selected service and its dependency graph.
        arguments: list[str] = compose_build_arguments(definition, compose_files, service)

        # Run the build with streamed output and a bounded diagnostic tail.
        return self._docker.run(
            arguments,
            operation = "build",
            environment = environment,
            capture = False,
            output = output,
        )

# Define the public API of the Compose CLI gateway.
__all__: list[str] = ["ComposeCli"]
