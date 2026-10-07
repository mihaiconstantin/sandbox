# Imports.
from __future__ import annotations

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent an unresolvable recipe source.
class RecipeError(InputError):
    # No additional behavior.
    pass


# Represent a recipe source that cannot be resolved.
class RecipeUnresolved(RecipeError):
    # Construct the error from its field and message.
    def __init__(self, field: str, message: str) -> None:
        # Record the neutral field path and message.
        self.field: str = field
        self.message: str = message

        # Initialize the error with the configuration-style text.
        super().__init__(f"{field or 'configuration'}: {message}")
