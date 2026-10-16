# Imports.
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.items import Table

# Import configuration document, path, registry, secret, and value helpers.
from sandbox.configuration import paths, registry, secrets
from sandbox.configuration.documents import default_file_mode
from sandbox.configuration.secrets import validate_secret_file
from sandbox.domain.registry import CatalogueRegistration, SecretBinding

# Import typed configuration errors.
from sandbox.errors.catalogues import RegistryError

# Import identifier validation.
from sandbox.validation.identifiers import validate_identifier


# Own the configuration home's `catalogues.toml` document and its atomic updates.
class ConfigurationStore:
    # Bind the store to one configuration home without resolving or reading it.
    def __init__(self, home: Path) -> None:
        # Retain the requested home and defer expansion until first use.
        self._home: Path = home
        self._resolved_home: Path | None = None

    # Resolve the configuration home on first access.
    @property
    def home(self) -> Path:
        # Resolve and cache the expanded configuration home.
        if self._resolved_home is None:
            self._resolved_home = paths.resolved_home(self._home)

        # Return the resolved configuration home.
        return self._resolved_home
