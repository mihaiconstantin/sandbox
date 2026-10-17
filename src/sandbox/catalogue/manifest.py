# Imports.
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.recipe import Recipe

# Import typed configuration errors and models.
from sandbox.errors.configuration import ConfigurationError

# The manifest filename expected in every catalogue directory.
MANIFEST_FILENAME: str = "catalogue.toml"


# Resolve a catalogue directory without exposing raw filesystem errors.
def _resolve_catalogue_directory(directory: Path) -> Path:
    # Resolve the catalogue directory to an absolute path.
    try:
        resolved: Path = directory.expanduser().resolve(strict = True)

    # If the catalogue path cannot be resolved.
    except OSError as error:
        # Throw.
        raise ConfigurationError("", f"Catalogue path `{directory}` cannot be resolved: {error}.") from error

    # If the catalogue path is not a directory.
    if not resolved.is_dir():
        # Throw.
        raise ConfigurationError("", f"Catalogue path `{resolved}` is not a directory.")

    # Return the resolved catalogue directory.
    return resolved


# Load and validate the manifest of a catalogue directory.
def load_catalogue(directory: Path) -> Catalogue:
    # Resolve the catalogue directory to an absolute path.
    directory = _resolve_catalogue_directory(directory)

    # Compute the manifest path.
    manifest: Path = directory / MANIFEST_FILENAME

    # If the manifest does not exist.
    if not manifest.exists() and not manifest.is_symlink():
        # Throw.
        raise ConfigurationError("", f"Catalogue manifest `{manifest}` does not exist.")

    # Resolve the manifest path.
    try:
        resolved_manifest: Path = manifest.resolve(strict = True)

    # If the manifest path cannot be resolved.
    except OSError as error:
        # Throw.
        raise ConfigurationError("", f"Catalogue manifest `{manifest}` cannot be resolved: {error}.") from error

    # If the resolved manifest is not a regular file.
    if not resolved_manifest.is_file():
        # Throw.
        raise ConfigurationError("", f"Manifest `{MANIFEST_FILENAME}` must be a regular file.")

    # If the manifest resolves outside the catalogue.
    if not resolved_manifest.is_relative_to(directory):
        # Throw.
        raise ConfigurationError("", f"Manifest `{MANIFEST_FILENAME}` must resolve inside the catalogue directory `{directory}`.")

    # Parse the manifest as TOML without exposing parser exceptions to callers.
    try:
        # Open the manifest in binary mode, as required by `tomllib`.
        with resolved_manifest.open("rb") as file:
            # Read the native TOML tables.
            configuration: dict[str, Any] = tomllib.load(file)

    # If the manifest is not valid TOML.
    except tomllib.TOMLDecodeError as error:
        # Throw.
        raise ConfigurationError("", f"Manifest `{MANIFEST_FILENAME}` at `{resolved_manifest}` is not valid TOML: {error}.") from None

    # If the manifest is not UTF-8 encoded.
    except UnicodeDecodeError:
        # Throw.
        raise ConfigurationError("", f"Manifest `{MANIFEST_FILENAME}` at `{resolved_manifest}` must be UTF-8 encoded.") from None

    # If the manifest cannot be read.
    except OSError as error:
        # Throw.
        raise ConfigurationError("", f"Manifest `{MANIFEST_FILENAME}` at `{resolved_manifest}` cannot be read: {error}.") from error

    # Validate the manifest and retain its typed declarations.
    catalogue: Catalogue = Catalogue.from_mapping(configuration)

    # Prepare the recipe iteration targets.
    name: str
    recipe: Recipe

    # Require every declared `docker` compose file to resolve inside this catalogue.


# Resolve a recipe's declared `docker` compose file inside a catalogue directory.
def resolve_compose_file(directory: Path, name: str, recipe: Recipe) -> Path:
    # Resolve the catalogue directory to an absolute path.
    directory = _resolve_catalogue_directory(directory)

    # Build the catalogue-relative path without reinterpreting manifest syntax.
    path: Path = directory.joinpath(*PurePosixPath(recipe.compose).parts)

    # If the declared `docker` compose file does not exist.
    if not path.exists():
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` does not exist.")

    # Resolve the `docker` compose path.
    try:
        resolved: Path = path.resolve(strict = True)

    # If the `docker` compose path cannot be resolved.
    except OSError as error:
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` cannot be resolved: {error}.") from error

    # If the `docker` compose file resolves outside the catalogue.
    if not resolved.is_relative_to(directory):
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` must resolve inside the catalogue directory.")

    # If the `docker` compose path is not a regular file.
    if not resolved.is_file():
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` must be a regular file.")

    # Return the resolved path used by later `docker` compose operations.
