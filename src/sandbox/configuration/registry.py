# Imports.
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.items import Table

# Import configuration document, path, and value helpers.
from sandbox.configuration import documents, paths
from sandbox.configuration.paths import (
    BUNDLED_CATALOGUE_TYPE,
    CATALOGUE_ROOT,
    DEFAULT_CATALOGUE_NAME,
    DEFAULT_CATALOGUE_PATH,
    GIT_CATALOGUE_TYPE,
    LOCAL_CATALOGUE_TYPE,
    catalogue_path,
    registry_path,
)
from sandbox.domain.registry import CatalogueRegistration

# Import errors and validation.
from sandbox.errors.catalogues import RegistryError
from sandbox.validation.identifiers import validate_identifier

# Define the documented registration fields.
REGISTRATION_FIELDS: frozenset[str] = frozenset({"type", "path"})


# Read the catalogue section of a parsed registry.
def read_catalogue_section(document: tomlkit.TOMLDocument, registry_file: Path) -> Mapping[str, object] | None:
    # Get the registered catalogues.
    catalogues: object = document.get("catalogues")

    # Return no section when it is absent.
    if catalogues is None:
        # Return no section.
        return None

    # If the section is invalid.
    if not isinstance(catalogues, Mapping):
        # Throw.
        raise RegistryError(f"Invalid `catalogues` section in `{registry_file}`.")

    # Return the validated section.
    return catalogues
