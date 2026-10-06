# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError


# Represent a failed box creation or postcondition.
class CreateError(SandboxError):
    # No additional behavior.
    pass
