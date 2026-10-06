# Imports.
from __future__ import annotations

# Import the input compatibility base.
from sandbox.errors.base import InputError


# Represent an unresolvable recipe source.
class RecipeError(InputError):
    # No additional behavior.
    pass
