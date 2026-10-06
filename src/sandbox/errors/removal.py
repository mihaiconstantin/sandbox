# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a failed ownership check or removal postcondition.
class RemovalError(SandboxError):
    # No additional behavior.
    pass
