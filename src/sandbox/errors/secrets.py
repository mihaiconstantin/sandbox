# Imports.
from __future__ import annotations

from pathlib import Path

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent invalid secret configuration.
class SecretError(InputError):
    # No additional behavior.
    pass


# Represent a recipe-required secret without a user binding.
class MissingSecret(SecretError):
    # Construct the error from its catalogue, alias, and recipe.
    def __init__(self, catalogue: str, alias: str, recipe: str) -> None:
        # Record the secret resolution facts.
        self.catalogue: str = catalogue
        self.alias: str = alias
        self.recipe: str = recipe

        # Initialize the error with the neutral missing-secret text.
        super().__init__(f"Secret `{alias}` in catalogue `{catalogue}` is not configured.")


# Represent an unusable secret file binding.
class SecretFileError(SecretError):
    # Construct the error from its path and reason.
    def __init__(self, path: Path, reason: str) -> None:
        # Record the secret file facts.
        self.path: Path = path
        self.reason: str = reason

        # Initialize the error with the neutral unusable-file text.
        super().__init__(f"Secret file `{path}` is unusable: {reason}.")
