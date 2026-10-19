# Imports.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Import the neutral output contract and its silent default.
from sandbox.ports.output import SILENT, OutputSink

# Bound every diagnostic line that can cross the public boundary.
DIAGNOSTIC_LIMIT: int = 4096


# Record the completed state of one child command.
@dataclass(frozen = True, slots = True)
class CommandResult:
    # Record the executed argument vector.
    arguments: tuple[str, ...]

    # Record the raw process status without normalizing a positive value.
    returncode: int

    # Record the captured or tailed standard output as raw bytes.
    stdout: bytes = b""

    # Record the captured or tailed standard error as raw bytes.
    stderr: bytes = b""

    def __post_init__(self) -> None:
        # Require an immutable argument vector.
        if (
            not isinstance(self.arguments, tuple)
            or any(not isinstance(argument, str) for argument in self.arguments)
        ):
            # Throw.
            raise ValueError("CommandResult.arguments must be a tuple of strings.")

        # Require an exact integer status.
        if type(self.returncode) is not int:
            # Throw.
            raise ValueError("CommandResult.returncode must be an integer.")

        # Require raw byte streams.
        if not isinstance(self.stdout, bytes) or not isinstance(self.stderr, bytes):
            # Throw.
            raise ValueError("CommandResult.stdout and CommandResult.stderr must be bytes.")

    @property
    def diagnostic(self) -> str:
        # Prefer the last non-empty standard-error line and fall back to standard output.
        for stream in (self.stderr, self.stdout):
            # Decode invalid partial UTF-8 without raising across the boundary.
            text: str = stream.decode("utf-8", errors = "replace")

            # Select the last non-empty line.
            lines: list[str] = [line.strip() for line in text.splitlines() if line.strip()]

            # Return the bounded diagnostic when this stream carried one.
            if lines:
                # Bound the diagnostic to a single stable line.
                return lines[-1][:DIAGNOSTIC_LIMIT]

        # Report an empty diagnostic when both streams were empty.
        return ""


# Define the process-execution seam shared by the Docker integration.
@runtime_checkable
class CommandRunner(Protocol):
    # Run one non-interactive command with captured or streamed binary pipes.
    def run(
        self,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        capture: bool = True,
        output: OutputSink = SILENT,
    ) -> CommandResult: ...
