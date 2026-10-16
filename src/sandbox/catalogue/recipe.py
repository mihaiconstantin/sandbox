# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.fields import validate_fields, validate_string
from sandbox.validation.identifiers import validate_identifier
