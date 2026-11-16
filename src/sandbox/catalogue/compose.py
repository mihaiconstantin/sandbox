# Imports.
from pathlib import Path, PurePosixPath

# Import catalogue declarations.
from sandbox.catalogue.recipe import Recipe

# Import errors.
from sandbox.errors.configuration import ConfigurationError


# Resolve one catalogue directory without exposing raw filesystem errors.
def resolve_catalogue_directory(directory: Path) -> Path:
    # Resolve the catalogue directory.
    try:
        # Resolve the real directory.
        resolved: Path = directory.expanduser().resolve(strict = True)

    # If the path cannot be resolved.
    except OSError as error:
        # Throw.
        raise ConfigurationError("", f"Catalogue path `{directory}` cannot be resolved: {error}.") from error

    # If the path is not a directory.
    if not resolved.is_dir():
        # Throw.
        raise ConfigurationError("", f"Catalogue path `{resolved}` is not a directory.")

    # Return the resolved directory.
    return resolved


# Resolve one recipe's compose path inside a catalogue directory.
def resolve_compose_file(directory: Path, name: str, recipe: Recipe) -> Path:
    # Resolve the catalogue directory.
    directory = resolve_catalogue_directory(directory)

    # Build the catalogue-relative compose path.
    path: Path = directory.joinpath(*PurePosixPath(recipe.compose).parts)

    # If the compose file does not exist.
    if not path.exists():
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` does not exist.")

    # Resolve the compose path.
    try:
        # Resolve the real path.
        resolved: Path = path.resolve(strict = True)

    # If the compose path cannot be resolved.
    except OSError as error:
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` cannot be resolved: {error}.") from error

    # If the compose path escapes the catalogue directory.
    if not resolved.is_relative_to(directory):
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` must resolve inside the catalogue directory.")

    # If the compose path is not a regular file.
    if not resolved.is_file():
        # Throw.
        raise ConfigurationError(f"recipes.{name}.compose", f"Compose file `{recipe.compose}` must be a regular file.")

    # Return the resolved compose path.
    return resolved
