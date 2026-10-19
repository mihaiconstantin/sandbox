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
