# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.fields import validate_fields, validate_string
from sandbox.validation.identifiers import validate_identifier


# Represent a recipe declaration without loading files or resolving inheritance.
@dataclass(frozen = True)
class Recipe:
    compose: str
    service: str
    extends: str | None = None
    volumes: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    allow_root: bool = False
