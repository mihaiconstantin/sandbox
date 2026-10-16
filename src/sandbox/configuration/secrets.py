# Imports.
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

import tomlkit

# Import configuration path and registry helpers.
from sandbox.configuration import paths, registry
from sandbox.domain.registry import SecretBinding

# Import typed configuration errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.secrets import SecretFileError


# Validate a secret file that will be mounted into a container.
def validate_secret_file(path: Path) -> Path:
    # If the path cannot be inspected.
    try:
        is_file: bool = path.is_file()

    # If the operating system refuses the inspection.
    except OSError as error:
        # Throw.
        raise SecretFileError(path, f"cannot be inspected: {error.strerror or error}") from error

    # If the path is not a regular file.
    if not is_file:
        # Throw.
        raise SecretFileError(path, "does not exist or is not a regular file")

    # If the file is not readable.
    if not os.access(path, os.R_OK):
        # Throw.
        raise SecretFileError(path, "is not readable")

    # Return the validated path.
    return path
