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


# Represent a box that inspection proves absent.
class BoxNotFound(BoxLookupError):
    # Construct the error from the box name and optional backend label.
    def __init__(self, name: str, backend: str | None = None) -> None:
        # Record the box identity and backend label.
        self.name: str = name
        self.backend: str | None = backend

        # Initialize the error with a neutral missing-box message.
        super().__init__(f"Box `{name}` was not found.")


# Represent more than one managed instance for one box name.
class BoxAmbiguous(BoxLookupError):
    # Construct the error from the box name, candidate count, and optional backend label.
    def __init__(self, name: str, count: int, backend: str | None = None) -> None:
        # Record the box identity, candidate count, and backend label.
        self.name: str = name
        self.count: int = count
        self.backend: str | None = backend

        # Initialize the error with a neutral ambiguity message.
        super().__init__(f"Multiple boxes exist for project `{name}`.")


# Represent a partially created box that cannot start.
class BoxNotReady(BoxStateError):
    # No additional behavior.
    pass
