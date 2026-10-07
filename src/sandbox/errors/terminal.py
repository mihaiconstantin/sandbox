# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a missing interactive terminal capability.
class TerminalError(SandboxError):
    # No additional behavior.
    pass
