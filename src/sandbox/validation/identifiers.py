# Imports.
from __future__ import annotations

import re

# Import errors.
from sandbox.errors.configuration import ConfigurationError


# Validate identifiers using the shared lowercase namespace.
def validate_identifier(value: object, field: str) -> None:
    # If the identifier does not match the shared namespace.
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value) is None:
        # Throw.
        raise ConfigurationError(field, "Must start with a lowercase letter or digit and contain only lowercase letters, digits, hyphens, or underscores.")


# Validate a physical volume name using the Docker-compatible shared rule.
def validate_volume_name(value: object) -> None:
    # If the volume name does not match the Docker-compatible rule.
    if not isinstance(value, str) or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+", value) is None:
        # Throw.
        raise ConfigurationError("volume.name", "Must start with a letter or digit and contain only letters, digits, periods, hyphens, or underscores.")
