# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError


# Represent a failed recipe image build.
class BuildError(SandboxError):
    # No additional behavior.
    pass


# Represent a failed recipe image build with its command facts.
class BuildFailed(BuildError):
    # Construct the error from the command failure.
    def __init__(self, failure: CommandFailure) -> None:
        # Record the command failure facts.
        self.failure: CommandFailure = failure

        # Initialize the error with a neutral build message.
        super().__init__(f"Build failed with exit code {failure.exit_code}.")
