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
