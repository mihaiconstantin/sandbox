# Imports.
from collections.abc import Mapping
from typing import Any

# Import errors.
from sandbox.errors.configuration import ConfigurationError


# Require a value to be a mapping.
def require_mapping(value: object, field: str, *, message: str = "Must be a mapping.") -> Mapping[str, Any]:
    # If the value is not a mapping.
    if not isinstance(value, Mapping):
        # Throw.
        raise ConfigurationError(field, message)

    # Return the validated mapping.
    return value
