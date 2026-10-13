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


# Build a registration value from one stored registration table.
def registration_value(name: str, registration: object, home: Path, registry_file: Path) -> CatalogueRegistration:
    # If the registration is not a table.
    if not isinstance(registration, Mapping):
        # Throw.
        raise RegistryError(f"Catalogue `{name}` has an invalid registration in `{registry_file}`.")

    # Reject fields outside the documented registration schema.
    unsupported: list[str] = sorted(str(field) for field in registration if field not in REGISTRATION_FIELDS)

    # If the registration contains unsupported fields.
    if unsupported:
        # Throw.
        raise RegistryError(f"Catalogue `{name}` registration in `{registry_file}` contains unsupported field(s): {', '.join(f'`{field}`' for field in unsupported)}.")

    # Get the registered origin.
    registered_type: object = registration.get("type")

    # If the origin is not a nonempty string.
    if not isinstance(registered_type, str) or not registered_type:
        # Throw.
        raise RegistryError(f"Catalogue `{name}` has an invalid type in `{registry_file}`.")

    # Get the registered path.
    registered_path: object = registration.get("path")

    # If the path is not a nonempty string.
    if not isinstance(registered_path, str) or not registered_path:
        # Throw.
        raise RegistryError(f"Catalogue `{name}` has an invalid registered path.")

    # Resolve the registered path relative to the configuration home.
