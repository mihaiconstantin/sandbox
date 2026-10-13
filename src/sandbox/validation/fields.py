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


# Validate a declaration's table, required fields, and allowed fields.
def validate_fields(configuration: object, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> Mapping[str, Any]:
    # Require a mapping before reading fields.
    configuration = require_mapping(configuration, "")

    # Report unknown fields first so misspelled options are not silently ignored.
    for name in configuration:
        # If a field name is not a string.
        if not isinstance(name, str):
            # Throw.
            raise ConfigurationError("", "Field names must be strings.")

        # If the field is not allowed.
        if name not in required and name not in optional:
            # Throw.
            raise ConfigurationError(name, "Unknown field.")

    # Require explicit values for fields without defaults.
    for name in required:
        # If a required field is missing.
        if name not in configuration:
            # Throw.
            raise ConfigurationError(name, "Required field is missing.")

    # Return the validated table.
    return configuration


# Require a nonblank string without coercing or trimming the supplied value.
def validate_string(value: object, field: str) -> None:
    # If the value is not a nonblank string.
    if not isinstance(value, str) or not value.strip():
        # Throw.
        raise ConfigurationError(field, "Must be a nonblank string.")
