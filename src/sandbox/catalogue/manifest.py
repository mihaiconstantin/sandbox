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
