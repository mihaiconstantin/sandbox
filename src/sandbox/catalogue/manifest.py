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
