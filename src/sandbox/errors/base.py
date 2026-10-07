# Imports.
from __future__ import annotations

from dataclasses import dataclass


# Represent an expected failure that crosses the public boundary.
class SandboxError(Exception):
    # No additional behavior.
    pass


# Represent invalid caller input with the documented builtin compatibility base.
class InputError(SandboxError, ValueError):
    # No additional behavior.
    pass


# Record the structured facts of one failed command.
@dataclass(frozen = True, slots = True)
class CommandFailure:
    # Identify the adapter that ran the command.
    backend: str

    # Name the neutral operation that failed.
    operation: str

    # Record the argument vector when the adapter has one.
    command: tuple[str, ...] | None

    # Record the adapter-normalized exit status.
    exit_code: int

    # Record the bounded diagnostic line.
    diagnostic: str

    # Report whether the command exceeded its deadline.
    timed_out: bool = False
