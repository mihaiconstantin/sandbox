# Imports.
import shutil
from dataclasses import replace
from pathlib import Path

# Import the registry module so tests can replace its atomic writer.
from sandbox.configuration import registry

# Import the neutral registry-facing values.
from sandbox.domain.registry import CatalogueBinding, CatalogueRegistration

# Import typed configuration errors and the shared removal postcondition error.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.removal import IncompleteRemoval
