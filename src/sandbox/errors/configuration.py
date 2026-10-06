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

    # Return a new error with a nested prefix applied.
    def with_prefix(self, prefix: str) -> ConfigurationError:
        # Join the prefix and field path.
        field: str = f"{prefix}.{self.field}" if self.field else prefix

        # Return a new error so the original keeps its attribution.
        return ConfigurationError(field, self.message)
