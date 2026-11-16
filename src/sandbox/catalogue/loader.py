# Imports.
import re
import tomllib
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TypeVar

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.compose import resolve_catalogue_directory, resolve_compose_file
from sandbox.catalogue.manifest import CATALOGUE_MANIFEST_FILENAME, manifest_path
from sandbox.catalogue.recipe import Recipe

# Import domain values.
from sandbox.domain.volume import VolumeDeclaration

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation import fields, identifiers


# Define the generic declaration type parsed from one manifest table.
Declaration = TypeVar("Declaration")


# Load and parse catalogue manifests.
class CatalogueLoader:
    # Read and parse one manifest file.
    def _read_manifest(self: "CatalogueLoader", directory: Path) -> dict[str, object]:
        # Compute the manifest path.
        manifest: Path = manifest_path(directory)

        # If the manifest does not exist.
        if not manifest.exists() and not manifest.is_symlink():
            # Throw.
            raise ConfigurationError("", f"Catalogue manifest `{manifest}` does not exist.")

        # Resolve the manifest path.
        try:
            # Resolve the real manifest path.
            resolved_manifest: Path = manifest.resolve(strict = True)

        # If the manifest cannot be resolved.
        except OSError as error:
            # Throw.
            raise ConfigurationError("", f"Catalogue manifest `{manifest}` cannot be resolved: {error}.") from error

        # If the manifest is not a regular file.
        if not resolved_manifest.is_file():
            # Throw.
            raise ConfigurationError("", f"Manifest `{CATALOGUE_MANIFEST_FILENAME}` must be a regular file.")

        # If the manifest escapes the catalogue directory.
        if not resolved_manifest.is_relative_to(directory):
            # Throw.
            raise ConfigurationError("", f"Manifest `{CATALOGUE_MANIFEST_FILENAME}` must resolve inside the catalogue directory `{directory}`.")

        # Parse the manifest.
        try:
            # Open the manifest in binary mode.
            with resolved_manifest.open("rb") as file:
                # Read the native TOML tables.
                configuration: dict[str, object] = tomllib.load(file)

        # If the manifest is not valid TOML.
        except tomllib.TOMLDecodeError as error:
            # Throw.
            raise ConfigurationError("", f"Manifest `{CATALOGUE_MANIFEST_FILENAME}` at `{resolved_manifest}` is not valid TOML: {error}.") from None

        # If the manifest is not UTF-8 encoded.
        except UnicodeDecodeError:
            # Throw.
            raise ConfigurationError("", f"Manifest `{CATALOGUE_MANIFEST_FILENAME}` at `{resolved_manifest}` must be UTF-8 encoded.") from None

        # If the manifest cannot be read.
        except OSError as error:
            # Throw.
            raise ConfigurationError("", f"Manifest `{CATALOGUE_MANIFEST_FILENAME}` at `{resolved_manifest}` cannot be read: {error}.") from error

        # Return the parsed manifest.
        return configuration

    # Parse one volume declaration.
    def _parse_volume(self: "CatalogueLoader", configuration: object) -> VolumeDeclaration:
        # Validate the strict volume field set.
        values = fields.validate_fields(configuration, ("name", "scope", "target"))

        # Validate the physical volume name.
        fields.validate_string(values["name"], "name")

        # If the volume name is not a valid Docker volume name.
        if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+", values["name"]) is None:
            # Throw.
            raise ConfigurationError("name", "Must be a Docker volume name of at least two characters, starting with a letter or digit and containing only letters, digits, periods, hyphens, or underscores.")

        # Validate the explicit sharing scope.
        fields.validate_string(values["scope"], "scope")

        # If the sharing scope is unsupported.
        if values["scope"] != "shared":
            # Throw.
            raise ConfigurationError("scope", "Only `shared` scope is supported by schema version 1.")

        # Validate the literal absolute guest target.
        fields.validate_string(values["target"], "target")

        # Parse the literal absolute POSIX target.
        target: PurePosixPath = PurePosixPath(values["target"])

        # If the target is not a literal absolute POSIX path.
        if not target.is_absolute() or ".." in target.parts or "\\" in values["target"] or "\x00" in values["target"] or "$" in values["target"]:
            # Throw.
            raise ConfigurationError("target", "Must be a literal absolute POSIX container path without parent traversal, backslashes, NUL bytes, or dollar signs.")

        # Return the validated declaration.
        return VolumeDeclaration(
            name = values["name"],
            scope = values["scope"],
            target = values["target"],
        )

    # Parse one recipe declaration.
    def _parse_recipe(self: "CatalogueLoader", configuration: object) -> Recipe:
        # Validate the strict recipe field set.
        values = fields.validate_fields(configuration, ("compose", "service"), ("extends", "volumes", "secrets", "allow_root"))

        # If the parent is explicitly null.
        if "extends" in values and values["extends"] is None:
            # Throw.
            raise ConfigurationError("extends", "Must be a single parent recipe identifier when present.")

        # Build the validated recipe.
        return Recipe(
            compose = values["compose"],
            service = values["service"],
            extends = values.get("extends"),
            volumes = values.get("volumes", []),
            secrets = values.get("secrets", []),
            allow_root = values.get("allow_root", False),
        )

    # Parse one declaration table with field attribution.
    def _parse_declarations(
        self: "CatalogueLoader",
        configuration: object,
        field: str,
        message: str,
        parser: Callable[[object], Declaration],
    ) -> dict[str, Declaration]:
        # Require the declaration table.
        values = fields.require_mapping(configuration, field, message = message)

        # Prepare the parsed declaration table.
        declarations: dict[str, Declaration] = {}

        # For each declaration identifier and configuration.
        for name, declaration_configuration in values.items():
            # Prepare the declaration field name.
            field_name: str = f"{field}.{name}" if isinstance(name, str) else field

            # Validate the declaration identifier.
            identifiers.validate_identifier(name, field_name)

            # Parse the declaration.
            try:
                # Store the parsed declaration.
                declarations[name] = parser(declaration_configuration)

            # If the declaration is invalid.
            except ConfigurationError as error:
                # Prefix the error with the declaration identifier.
                raise error.with_prefix(field_name) from None

        # Return the parsed declarations.
        return declarations

    # Parse the recipe declarations.
    def _parse_recipes(self: "CatalogueLoader", configuration: object) -> dict[str, Recipe]:
        # Parse the recipes with field attribution.
        return self._parse_declarations(
            configuration,
            "recipes",
            "Must be a table of recipe declarations.",
            self._parse_recipe,
        )

    # Parse the volume declarations.
    def _parse_volumes(self: "CatalogueLoader", configuration: object) -> dict[str, VolumeDeclaration]:
        # Parse the volumes with field attribution.
        return self._parse_declarations(
            configuration,
            "volumes",
            "Must be a table of volume declarations.",
            self._parse_volume,
        )

    # Parse one catalogue declaration.
    def _parse_catalogue(self: "CatalogueLoader", configuration: object) -> Catalogue:
        # Validate the strict catalogue field set.
        values = fields.validate_fields(configuration, ("catalogue", "recipes"), ("volumes",))

        # Validate the strict metadata field set.
        try:
            # Parse the catalogue metadata.
            metadata = fields.validate_fields(values["catalogue"], ("name", "version", "schema_version"), ("default_recipe",))

        # If the metadata is invalid.
        except ConfigurationError as error:
            # Prefix the metadata field with its table.
            raise error.with_prefix("catalogue") from None

        # Parse the declarations.
        recipes: dict[str, Recipe] = self._parse_recipes(values["recipes"])
        volumes: dict[str, VolumeDeclaration] = self._parse_volumes(values.get("volumes", {}))

        # Return the validated catalogue.
        return Catalogue(
            name = metadata["name"],
            version = metadata["version"],
            schema_version = metadata["schema_version"],
            recipes = recipes,
            volumes = volumes,
            default_recipe = metadata.get("default_recipe"),
        )

    # Require every declared compose file to resolve inside the catalogue.
    def _validate_compose_files(self: "CatalogueLoader", directory: Path, catalogue: Catalogue) -> None:
        # For each recipe declaration.
        for name, recipe in catalogue.recipes.items():
            # Resolve the recipe compose file.
            resolve_compose_file(directory, name, recipe)

    # Load and validate one catalogue directory.
    def load(self: "CatalogueLoader", directory: Path) -> Catalogue:
        # Resolve the catalogue directory.
        directory = resolve_catalogue_directory(directory)

        # Read the manifest.
        configuration: dict[str, object] = self._read_manifest(directory)

        # Parse the catalogue declarations.
        catalogue: Catalogue = self._parse_catalogue(configuration)

        # Require every declared compose file to resolve inside the catalogue.
        self._validate_compose_files(directory, catalogue)

        # Return the validated catalogue.
        return catalogue

    # Parse one catalogue mapping without reading the filesystem.
    def parse_catalogue(self: "CatalogueLoader", configuration: object) -> Catalogue:
        # Return the parsed catalogue.
        return self._parse_catalogue(configuration)

    # Parse one recipe mapping without reading the filesystem.
    def parse_recipe(self: "CatalogueLoader", configuration: object) -> Recipe:
        # Return the parsed recipe.
        return self._parse_recipe(configuration)
