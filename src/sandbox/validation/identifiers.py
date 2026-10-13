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
