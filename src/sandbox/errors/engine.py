# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError


# Represent an engine or adapter operation failure.
class EngineError(SandboxError):
    # No additional behavior.
    pass
