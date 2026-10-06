# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a failed lookup for one managed box.
class BoxLookupError(SandboxError):
    # No additional behavior.
    pass


# Represent a box that cannot perform an operation in its observed state.
class BoxStateError(SandboxError):
    # Construct the error from the box identity and its observed state.
    def __init__(self, name: str, state: str | None = None, detail: str = "") -> None:
        # Record the box state facts.
        self.name: str = name
        self.state: str | None = state
        self.detail: str = detail

        # Initialize the error with a neutral fallback message.
        super().__init__(detail or f"Box `{name}` is not in the required state.")
