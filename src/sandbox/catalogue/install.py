# Imports.
import os
import shutil
import tempfile
from collections.abc import MutableMapping
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from sandbox.catalogue import manifest, sources

# Import models.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.configuration.store import ConfigurationStore

# Import errors and helpers.
from sandbox.errors.catalogues import CatalogueInstallError
