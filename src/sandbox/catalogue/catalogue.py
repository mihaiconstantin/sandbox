# Imports.
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
import re
from types import MappingProxyType
from typing import Any

# Import catalogue declarations.
from sandbox.catalogue.recipe import Recipe

# Import the neutral volume declaration.
from sandbox.domain.volume import VolumeDeclaration

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.fields import require_mapping, validate_fields, validate_string
from sandbox.validation.identifiers import validate_identifier


# Parse and validate one manifest volume declaration with field attribution.
def _parse_volume_declaration(configuration: object) -> VolumeDeclaration:
    # Validate the strict volume field set.
    configuration = validate_fields(configuration, ("name", "scope", "target"))

    # Validate the physical volume name.
    validate_string(configuration["name"], "name")
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+", configuration["name"]) is None:
        # Throw.
        raise ConfigurationError("name", "Must be a Docker volume name of at least two characters, starting with a letter or digit and containing only letters, digits, periods, hyphens, or underscores.")

    # Validate the explicit sharing scope.
    validate_string(configuration["scope"], "scope")
    if configuration["scope"] != "shared":
        # Throw.
        raise ConfigurationError("scope", "Only `shared` scope is supported by schema version 1.")

    # Validate the literal absolute guest target.
    validate_string(configuration["target"], "target")
    target: PurePosixPath = PurePosixPath(configuration["target"])
    if not target.is_absolute() or ".." in target.parts or "\\" in configuration["target"] or "\x00" in configuration["target"] or "$" in configuration["target"]:
        # Throw.
        raise ConfigurationError("target", "Must be a literal absolute POSIX container path without parent traversal, backslashes, NUL bytes, or dollar signs.")

    # Build the validated neutral declaration.
    return VolumeDeclaration(name = configuration["name"], scope = configuration["scope"], target = configuration["target"])
