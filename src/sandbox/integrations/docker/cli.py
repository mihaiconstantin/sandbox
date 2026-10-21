# Imports.
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# Import the public error values raised by the gateway.
from sandbox.errors.base import CommandFailure
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Import the process seam and its result value.
from sandbox.integrations.docker.command import CommandResult, CommandRunner

# Import the neutral output contract.
from sandbox.ports.output import SILENT, OutputSink


# Run Docker CLI commands and translate their failures once.
class DockerCli:
    # Construct the gateway around one process runner.
    def __init__(self, runner: CommandRunner) -> None:
        # Record the injected runner.
        self._runner: CommandRunner = runner

    # Run one command without translating a non-zero status.
    def run(
        self,
        arguments: Sequence[str],
        *,
        operation: str,
        environment: Mapping[str, str] | None = None,
        capture: bool = True,
        output: OutputSink = SILENT,
    ) -> CommandResult:
        # Normalize the argument vector.
        command: tuple[str, ...] = tuple(arguments)

        # Execute through the injected runner.
        try:
            # Run the child with the requested capture and output behavior.
            return self._runner.run(command, environment = environment, capture = capture, output = output)

        # A missing or unusable executable is a lazy host prerequisite, not an engine failure.
        except (FileNotFoundError, PermissionError, OSError) as error:
            # Choose the prerequisite kind from the OS failure.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Translate the host failure without leaking the raw exception.
            raise PrerequisiteError(
                "docker",
                kind,
                operation = operation,
                diagnostic = str(error)[:4096],
                hint = "Install Docker and ensure the `docker` executable is available on PATH.",
            ) from error

    # Run one interactive command with inherited standard streams.
    def run_interactive(
        self,
        arguments: Sequence[str],
        *,
        operation: str,
        environment: Mapping[str, str] | None = None,
    ) -> CommandResult:
        # Execute through the injected runner with inherited streams.
        try:
            # Preserve the terminal and the child status unchanged.
            return self._runner.run_interactive(tuple(arguments), environment = environment)

        # Translate a missing executable once.
        except (FileNotFoundError, PermissionError, OSError) as error:
            # Choose the prerequisite kind from the OS failure.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Translate the host failure without leaking the raw exception.
            raise PrerequisiteError("docker", kind, operation = operation, diagnostic = str(error)[:4096]) from error
