# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError

# Import the shared ownership category.
from sandbox.errors.ownership import OwnershipViolation


# Represent a failed shared-volume operation.
class VolumeError(SandboxError):
    # No additional behavior.
    pass
