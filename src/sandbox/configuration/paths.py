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
