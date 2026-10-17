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


# Represent a validated manifest's declarations, independently of its filesystem.
@dataclass(frozen = True)
class Catalogue:
    name: str
    version: str
    schema_version: int
    recipes: Mapping[str, Recipe]
    volumes: Mapping[str, VolumeDeclaration] = field(default_factory = dict)
    default_recipe: str | None = None

    def __post_init__(self) -> None:
        # Catalogue versions describe definitions, not dependency constraints.
        validate_identifier(self.name, "catalogue.name")
        validate_string(self.version, "catalogue.version")

        # If the schema version is not an integer.
        if type(self.schema_version) is not int:
            # Throw.
            raise ConfigurationError("catalogue.schema_version", "Must be an integer.")

        # If the schema version is unsupported.
        if self.schema_version != 1:
            # Throw.
            raise ConfigurationError("catalogue.schema_version", f"Unsupported schema version `{self.schema_version}`; expected `1`.")

        # Require a table of recipe declarations.
        require_mapping(self.recipes, "recipes", message="Must be a table of recipe declarations.")

        # Copy the table before validating its declarations.
        recipes: dict[str, Recipe] = dict(self.recipes)

        # If no recipes are declared.
        if not recipes:
            # Throw.
            raise ConfigurationError("recipes", "Must declare at least one recipe.")

        # Validate each recipe identifier and declaration.
        for name, recipe in recipes.items():
            field_name: str = f"recipes.{name}" if isinstance(name, str) else "recipes"
            validate_identifier(name, field_name)

            # If the recipe declaration is invalid.
            if not isinstance(recipe, Recipe):
                # Throw.
                raise ConfigurationError(field_name, "Must be a Recipe declaration.")

        # Publish the validated recipe table as an immutable snapshot.
        object.__setattr__(self, "recipes", MappingProxyType(recipes))

        # If a default recipe is declared.
        if self.default_recipe is not None:
            # Require a nonblank recipe name.
            validate_string(self.default_recipe, "catalogue.default_recipe")

            # Require the default recipe to be declared in this catalogue.
            if self.default_recipe not in recipes:
                # Throw.
                raise ConfigurationError("catalogue.default_recipe", f"Recipe `{self.default_recipe}` is not declared in the catalogue.")

        # Require a table of volume declarations.
        require_mapping(self.volumes, "volumes", message="Must be a table of volume declarations.")

        # Copy the table before validating its declarations.
        volumes: dict[str, VolumeDeclaration] = dict(self.volumes)

        # Volume aliases are local to this catalogue, even when physical names coincide.
        # For each volume identifier and declaration.
