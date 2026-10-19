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


# Install catalogues below the `sandbox` catalogue root.
class CatalogueInstaller:
    # Prepare an installer for a `sandbox` directory.
    def __init__(self, home: Path, store: ConfigurationStore | None = None) -> None:
        # Resolve the `sandbox` directory.
        self.home: Path = home.expanduser().resolve()

        # Bind the installer to the configuration store.
        self.store: ConfigurationStore = store if store is not None else ConfigurationStore(self.home)
