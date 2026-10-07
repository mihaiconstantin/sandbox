# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError


# Represent a failed box creation or postcondition.
class CreateError(SandboxError):
    # No additional behavior.
    pass


# Represent a failed box creation with its command facts.
class CreateFailed(CreateError):
    # Construct the error from the command failure.
    def __init__(self, failure: CommandFailure) -> None:
        # Record the command failure facts.
        self.failure: CommandFailure = failure

        # Initialize the error with a neutral creation message.
        super().__init__(f"Box creation failed with exit code {failure.exit_code}.")


# Represent a box creation that did not satisfy its postcondition.
class CreatePostconditionFailed(CreateError):
    # Construct the error from the box name and optional backend label.
    def __init__(self, name: str, backend: str | None = None) -> None:
        # Record the box identity and backend label.
        self.name: str = name
        self.backend: str | None = backend

        # Initialize the error with a neutral postcondition message.
        super().__init__(f"Box `{name}` was not created: no managed instance was observed.")
