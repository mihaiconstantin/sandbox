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
