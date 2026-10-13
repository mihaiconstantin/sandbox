# Imports.
import os
import tempfile
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

# Import typed configuration errors.
from sandbox.errors.catalogues import RegistryError

# Define the permission bits used for a newly created registry before the umask.
DEFAULT_REGISTRY_BITS: int = 0o666


# Compute the mode a regular file receives under the current process umask.
def default_file_mode() -> int:
    # Read and restore the process umask.
    current: int = os.umask(0)
    os.umask(current)

    # Apply the umask to the default file bits.
    return DEFAULT_REGISTRY_BITS & ~current
