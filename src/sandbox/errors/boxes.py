# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a failed lookup for one managed box.
class BoxLookupError(SandboxError):
    # No additional behavior.
    pass
