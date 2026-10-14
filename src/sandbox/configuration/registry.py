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
    resolved_path: Path = paths.resolve_registered_path(home, registered_path)

    # Compute the canonical managed catalogue path.
    canonical_path: Path = (paths.resolved_home(home) / CATALOGUE_ROOT / name).resolve()

    # If the registration does not use the canonical managed path.
    if resolved_path != canonical_path:
        # Throw.
        raise RegistryError(f"Catalogue `{name}` registration in `{registry_file}` uses the noncanonical path `{registered_path}`; expected `{CATALOGUE_ROOT}/{name}`.")

    # Return the registration with its resolved path.
    return CatalogueRegistration(name, registered_type, resolved_path)


# List every registration in name order with resolved absolute paths.
def read_registrations(document: tomlkit.TOMLDocument, home: Path, registry_file: Path) -> tuple[CatalogueRegistration, ...]:
    # Read the catalogue section.
    catalogues: Mapping[str, object] | None = read_catalogue_section(document, registry_file)

    # If no catalogues are registered.
    if catalogues is None:
        # Return no registrations.
        return ()

    # Prepare the registrations.
    registrations: list[CatalogueRegistration] = []

    # Read every catalogue registration.
    for name, registration in catalogues.items():
        # If the catalogue name is invalid.
        if not isinstance(name, str):
            # Throw.
            raise RegistryError(f"Invalid `catalogues` section in `{registry_file}`.")

        # Validate the catalogue name.
        try:
            validate_identifier(name, "catalogue")

        # If the catalogue name is invalid.
        except ValueError as error:
            # Throw.
            raise RegistryError(f"Invalid catalogue registration in `{registry_file}`: {error}") from None

        # Record the validated registration.
        registrations.append(registration_value(name, registration, home, registry_file))

    # Sort the registrations by catalogue name.
    registrations.sort(key = lambda item: item.name)

    # Return the registrations.
    return tuple(registrations)


# Read one registration by name, or report absence.
def read_registration(document: tomlkit.TOMLDocument, name: str, home: Path, registry_file: Path) -> CatalogueRegistration | None:
    # Read the catalogue section.
    catalogues: Mapping[str, object] | None = read_catalogue_section(document, registry_file)

    # If no catalogues are registered or the requested catalogue is absent.
    if catalogues is None or name not in catalogues:
        # Return no registration.
        return None

    # Return the validated registration.
    return registration_value(name, catalogues[name], home, registry_file)


# Load and parse a catalogue registry.
def load_registry(registry_file: Path) -> tomlkit.TOMLDocument:
    # Load the typed document through the shared registry document helper.
    return documents.load_document(registry_file)


# Write a catalogue registry atomically.
def write_registry_atomic(
    registry_file: Path,
    registry: tomlkit.TOMLDocument,
    replace: Any = None,
    *,
    new_mode: int | None = None,
) -> None:
    # Resolve the replacement operation in this module so callers can substitute it.
    replacement: Any = os.replace if replace is None else replace

    # Publish the registry through the shared atomic document writer.
    documents.write_document_atomic(registry_file, registry, replacement, new_mode = new_mode)


# Read or create the catalogue section of a registration document.
def writable_catalogues(document: tomlkit.TOMLDocument, registry_file: Path) -> Table:
    # Get the registered catalogues.
    catalogues: object = document.get("catalogues")

    # If the `catalogues` section is missing.
    if catalogues is None:
        # Create it.
        catalogues = tomlkit.table()
        document.add("catalogues", catalogues)

    # If the `catalogues` section is invalid.
    elif not isinstance(catalogues, MutableMapping):
        # Throw.
        raise RegistryError(f"Invalid `catalogues` section in `{registry_file}`.")

    # Return the writable section.
    return cast(Table, catalogues)


# Prepare a registry document with a catalogue registration.
def registration_document(home: Path, registry_file: Path, name: str, origin: str, force: bool) -> tomlkit.TOMLDocument:
    # Validate the catalogue name before using it in a registry path.
    validate_identifier(name, "catalogue")

    # Compute the canonical registered path.
    canonical_path: Path = paths.resolved_home(home) / CATALOGUE_ROOT / name

    # Compute the normalized registered path.
    normalized_path: str = f"{CATALOGUE_ROOT}/{name}"

    # If the registry file already exists.
    if registry_file.exists():
        # Parse the existing registry.
        document: tomlkit.TOMLDocument = load_registry(registry_file)

    # Otherwise.
    else:
        # Create a new registry document.
        document = tomlkit.document()

        # Add the conventional comment and separation.
        document.add(tomlkit.comment("Registered development `sandbox` catalogues."))
        document.add(tomlkit.nl())

    # Get or create the writable catalogue section.
    catalogues: MutableMapping[str, Any] = writable_catalogues(document, registry_file)

    # Get the existing catalogue registration.
    existing = catalogues.get(name)

    # If the catalogue is not registered.
