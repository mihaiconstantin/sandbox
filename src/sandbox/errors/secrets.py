# Imports.
from __future__ import annotations

from pathlib import Path

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent invalid secret configuration.
class SecretError(InputError):
    # No additional behavior.
    pass
