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
