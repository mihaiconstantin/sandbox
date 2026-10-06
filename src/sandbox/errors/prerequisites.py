# Imports.
from __future__ import annotations

from enum import StrEnum

# Import the public root.
from sandbox.errors.base import SandboxError


# Name the documented prerequisite failure kinds.
class PrerequisiteKind(StrEnum):
    # Report a tool that is not installed.
    MISSING = "missing"

    # Report a tool that is installed but cannot run.
    UNUSABLE = "unusable"

    # Report a tool whose version is unsupported.
    VERSION = "version"


# Represent a missing, unusable, or unsupported host tool.
class PrerequisiteError(SandboxError):
    # Construct the error from the tool and its structured facts.
    def __init__(
        self,
        tool: str,
        kind: PrerequisiteKind,
        *,
        requirement: str | None = None,
        found: str | None = None,
        operation: str | None = None,
        diagnostic: str = "",
        hint: str | None = None,
    ) -> None:
        # Record the prerequisite facts.
        self.tool: str = tool
        self.kind: PrerequisiteKind = kind
        self.requirement: str | None = requirement
        self.found: str | None = found
        self.operation: str | None = operation
        self.diagnostic: str = diagnostic
        self.hint: str | None = hint

        # Initialize the error with a neutral prerequisite message.
        super().__init__(f"Prerequisite `{tool}` is {kind.value}.")
