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


# Represent a volume referenced by containers.
class VolumeInUse(VolumeError):
    # Construct the error from the volume name and optional backend label.
    def __init__(self, name: str, backend: str | None = None) -> None:
        # Record the volume identity and backend label.
        self.name: str = name
        self.backend: str | None = backend

        # Initialize the error with a neutral in-use message.
        super().__init__(f"Volume `{name}` is still referenced.")


# Represent a volume whose references are unavailable.
class VolumeReferencesUnavailable(VolumeError):
    # Construct the error from the volume name.
    def __init__(self, name: str) -> None:
        # Record the volume identity.
        self.name: str = name

        # Initialize the error with a neutral unavailable-reference message.
        super().__init__(f"Volume `{name}` reference information is unavailable.")


# Represent a shared volume whose ownership cannot be verified.
class VolumeOwnershipError(OwnershipViolation):
    # Construct the error from the volume name.
    def __init__(self, name: str) -> None:
        # Record the volume identity.
        self.name: str = name

        # Initialize the ownership error for a volume.
        super().__init__("volume", name)
