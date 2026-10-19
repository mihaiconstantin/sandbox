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
