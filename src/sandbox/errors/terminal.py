# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a missing interactive terminal capability.
class TerminalError(SandboxError):
    # No additional behavior.
    pass


# Represent an interactive operation without a terminal.
class InteractiveTerminalRequired(TerminalError):
    # Construct the error from the optional backend label.
    def __init__(self, backend: str | None = None) -> None:
        # Record the backend label.
        self.backend: str | None = backend

        # Initialize the error with a neutral terminal message.
        super().__init__("The operation requires an interactive terminal.")
