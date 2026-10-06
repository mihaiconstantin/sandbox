# Imports.
from __future__ import annotations

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent invalid catalogue configuration.
class CatalogueError(InputError):
    # No additional behavior.
    pass


# Represent a failed catalogue installation.
class CatalogueInstallError(CatalogueError):
    # Construct the error from its message.
    def __init__(self, message: str) -> None:
        # Record the failure message.
        self.message: str = message

        # Initialize the error with the message.
        super().__init__(message)
