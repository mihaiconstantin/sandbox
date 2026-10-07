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


# Represent a volume that inspection proves absent.
class VolumeNotFound(VolumeError):
    # Construct the error from the volume name.
    def __init__(self, name: str) -> None:
        # Record the volume identity.
        self.name: str = name

        # Initialize the error with a neutral missing-volume message.
        super().__init__(f"Volume `{name}` no longer exists.")
