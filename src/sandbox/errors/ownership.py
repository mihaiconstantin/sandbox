# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a resource whose ownership cannot be verified.
class OwnershipViolation(SandboxError):
    # Construct the error from the resource kind and identifier.
    def __init__(self, resource_kind: str, identifier: str) -> None:
        # Record the neutral ownership facts.
        self.resource_kind: str = resource_kind
        self.identifier: str = identifier

        # Initialize the error with a neutral ownership message.
        super().__init__(f"Cannot verify sandbox ownership of {resource_kind} `{identifier}`.")
