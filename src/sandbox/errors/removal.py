# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a failed ownership check or removal postcondition.
class RemovalError(SandboxError):
    # No additional behavior.
    pass


# Represent a removal request with no managed resources.
class NothingToRemove(RemovalError):
    # Construct the error from the box name.
    def __init__(self, name: str) -> None:
        # Record the box identity.
        self.name: str = name

        # Initialize the error with a neutral missing-resource message.
        super().__init__(f"No sandbox resources exist for project `{name}`.")
