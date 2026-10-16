# Imports.
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

import tomlkit

# Import configuration path and registry helpers.
from sandbox.configuration import paths, registry
from sandbox.domain.registry import SecretBinding

# Import typed configuration errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.secrets import SecretFileError


# Validate a secret file that will be mounted into a container.
def validate_secret_file(path: Path) -> Path:
    # If the path cannot be inspected.
    try:
        is_file: bool = path.is_file()

    # If the operating system refuses the inspection.
    except OSError as error:
        # Throw.
        raise SecretFileError(path, f"cannot be inspected: {error.strerror or error}") from error

    # If the path is not a regular file.
    if not is_file:
        # Throw.
        raise SecretFileError(path, "does not exist or is not a regular file")

    # If the file is not readable.
    if not os.access(path, os.R_OK):
        # Throw.
        raise SecretFileError(path, "is not readable")

    # Return the validated path.
    return path


# Read the secret section of a parsed registry.
def read_secret_section(document: tomlkit.TOMLDocument, registry_file: Path) -> MutableMapping[str, Any] | None:
    # Get the secret bindings.
    secrets = document.get("secrets")

    # Return no section when it is absent.
    if secrets is None:
        # Return no section.
        return None

    # If the section is invalid.
    if not isinstance(secrets, MutableMapping):
        # Throw.
        raise RegistryError(f"Invalid `secrets` section in `{registry_file}`.")

    # Return the validated section.
    return secrets


# Read the bindings of one catalogue from the secret section.
def read_catalogue_bindings(secrets: MutableMapping[str, Any], catalogue: str, registry_file: Path) -> MutableMapping[str, Any] | None:
    # Get the catalogue bindings.
    bindings = secrets.get(catalogue)

    # Return no bindings when the catalogue has none.
    if bindings is None:
        # Return no bindings.
        return None

    # If the catalogue bindings are invalid.
    if not isinstance(bindings, MutableMapping):
        # Throw.
        raise RegistryError(f"Invalid `secrets.{catalogue}` section in `{registry_file}`.")

    # Return the validated bindings.
    return bindings


# Read one binding alias from a catalogue binding section.
def read_binding(bindings: MutableMapping[str, Any], catalogue: str, alias: str, registry_file: Path) -> MutableMapping[str, Any] | None:
    # Get the requested binding.
    binding = bindings.get(alias)

    # Return no binding when the alias is absent.
    if binding is None:
        # Return no binding.
        return None

    # If the binding is invalid.
    if not isinstance(binding, MutableMapping):
        # Throw.
        raise RegistryError(f"Invalid `secrets.{catalogue}.{alias}` section in `{registry_file}`.")

    # Return the validated binding.
    return binding


# Resolve a binding file path relative to the configuration home.
def binding_path(binding: Mapping[str, Any], home: Path, catalogue: str, alias: str) -> Path:
    # Get the configured file path.
    file = binding.get("file")

    # If the binding file path is invalid.
    if not isinstance(file, str) or not file:
        # Throw.
        raise RegistryError(f"Secret `{catalogue}.{alias}` has an invalid `file` path.")

    # Return the resolved path.
    return paths.resolve_secret_path(home, file)


# List secret bindings in catalogue and alias order.
def read_bindings(document: tomlkit.TOMLDocument, home: Path, registry_file: Path, catalogue: str | None = None) -> tuple[SecretBinding, ...]:
    # Read the secret section.
    secrets: MutableMapping[str, Any] | None = read_secret_section(document, registry_file)

    # If no bindings exist.
    if secrets is None:
        # Return no bindings.
        return ()

    # Prepare the bindings.
    bindings: list[SecretBinding] = []

    # Read every catalogue binding section.
    for catalogue_name in secrets:
        # Validate the catalogue bindings.
        section: MutableMapping[str, Any] | None = read_catalogue_bindings(secrets, catalogue_name, registry_file)

        # If the catalogue has no bindings.
        if section is None:
            # Continue with the next catalogue.
            continue

        # Read every binding in the catalogue.
        for alias in section:
            # Validate the binding.
            resolved_binding: MutableMapping[str, Any] | None = read_binding(section, catalogue_name, alias, registry_file)

            # If the binding is absent.
            if resolved_binding is None:
                # Continue with the next binding.
                continue

            # Resolve the binding path.
            path: Path = binding_path(resolved_binding, home, catalogue_name, alias)

            # Keep only the requested catalogue bindings.
            if catalogue is not None and catalogue_name != catalogue:
                # Continue with the next binding.
                continue

            # Record the binding.
            bindings.append(SecretBinding(catalogue_name, alias, path))

    # Sort the bindings by catalogue and secret alias.
    bindings.sort(key = lambda item: (item.catalogue, item.alias))

    # Return the bindings.
    return tuple(bindings)


# Get or create the secret section of a configuration document.
def ensure_secret_section(document: tomlkit.TOMLDocument, registry_file: Path) -> MutableMapping[str, Any]:
    # Get the secret section.
    secrets = document.get("secrets")

    # If the secret section is missing.
    if secrets is None:
        # Create the secret section.
        secrets = tomlkit.table()
        document["secrets"] = secrets

    # If the secret section is invalid.
    elif not isinstance(secrets, MutableMapping):
        # Throw.
        raise RegistryError(f"Invalid `secrets` section in `{registry_file}`.")

    # Return the writable section.
    return secrets
