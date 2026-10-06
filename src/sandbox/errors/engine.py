# Imports.
from __future__ import annotations

# Import the public root and command failure facts.
from sandbox.errors.base import CommandFailure, SandboxError


# Represent an engine or adapter operation failure.
class EngineError(SandboxError):
    # No additional behavior.
    pass


# Represent an engine command failure with structured facts.
class EngineFailure(EngineError):
    # Construct the error from the command failure.
    def __init__(self, failure: CommandFailure) -> None:
        # Record the command failure facts.
        self.failure: CommandFailure = failure

        # Initialize the error with a neutral operation message.
        super().__init__(f"Operation `{failure.operation}` failed with exit code {failure.exit_code}.")
