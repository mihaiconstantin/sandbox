# Imports.
from __future__ import annotations

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent invalid configuration input with its field path and message.
class ConfigurationError(InputError):
    # Construct the error from its field and message.
    def __init__(self, field: str, message: str) -> None:
        # Record the neutral field path and message.
        self.field: str = field
        self.message: str = message

        # Initialize the error with the configuration-level fallback.
        super().__init__(f"{field or 'configuration'}: {message}")
