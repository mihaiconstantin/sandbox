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

    def __post_init__(self) -> None:
        # Require a nonblank `docker` compose filename.
        validate_string(self.compose, "compose")

        # If the `docker` compose filename is not portable.
        if "\\" in self.compose or ":" in self.compose or "\x00" in self.compose or self.compose.endswith("/"):
            # Throw.
            raise ConfigurationError("compose", "Must be a portable relative file path.")

        # Filesystem existence and symlink containment are checked by the loader.
        compose_path: PurePosixPath = PurePosixPath(self.compose)

        # If the `docker` compose path is absolute or traverses parents.
        if compose_path.is_absolute() or not compose_path.parts or ".." in compose_path.parts:
            # Throw.
            raise ConfigurationError("compose", "Must be a catalogue-relative file path without parent traversal.")

        # `docker` compose service names use a different namespace from recipe identifiers.
        validate_string(self.service, "service")

        # If the service name is invalid.
        if re.fullmatch(r"[a-zA-Z0-9._-]+", self.service) is None:
            # Throw.
            raise ConfigurationError("service", "Must be a literal Compose service name containing only letters, digits, periods, hyphens, or underscores.")

        # If the recipe declares a parent.
        if self.extends is not None:
            validate_identifier(self.extends, "extends")

        # Store requirements immutably and reject duplicates within this recipe.
        # If the volumes value is not a tuple.
