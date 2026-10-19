# Imports.
from pathlib import Path

# Import identifier validation.
from sandbox.validation.identifiers import validate_identifier

# Define the `sandbox`-managed catalogue root, the default catalogue name, and its registered location.
CATALOGUE_ROOT: str = "catalogues"
DEFAULT_CATALOGUE_NAME: str = "default"
DEFAULT_CATALOGUE_PATH: str = f"{CATALOGUE_ROOT}/{DEFAULT_CATALOGUE_NAME}"

# Define the supported catalogue registration types.
BUNDLED_CATALOGUE_TYPE: str = "bundled"
LOCAL_CATALOGUE_TYPE: str = "local"
GIT_CATALOGUE_TYPE: str = "git"


# Expand and resolve a configuration home without requiring it to exist.
def resolved_home(home: Path) -> Path:
    # Return the absolute normalized home.
    return home.expanduser().resolve()


# Compute the path to a `sandbox` catalogue registry.
def registry_path(home: Path) -> Path:
    # Return the registry path inside the `sandbox` directory.
    return home / "catalogues.toml"


# Compute the path to a `sandbox`-managed catalogue.
def catalogue_path(home: Path, name: str) -> Path:
    # Validate the catalogue name before using it in a path.
    validate_identifier(name, "catalogue")

    # Return the catalogue path inside the resolved `sandbox` directory.
    return resolved_home(home) / CATALOGUE_ROOT / name


# Resolve a stored registration path relative to the configuration home.
def resolve_registered_path(home: Path, value: str) -> Path:
    # Interpret the stored path.
    path: Path = Path(value)

    # Resolve a relative path against the resolved configuration home.
    if not path.is_absolute():
        path = resolved_home(home) / path

    # Return the absolute normalized path.
    return path.resolve()


# Resolve a stored secret binding path relative to the configuration home.
def resolve_secret_path(home: Path, value: str) -> Path:
    # Expand a user-directory binding path.
    path: Path = Path(value).expanduser()

    # Resolve a relative path against the resolved configuration home.
    if not path.is_absolute():
        path = resolved_home(home) / path

    # Return the absolute normalized path.
    return path.resolve()
