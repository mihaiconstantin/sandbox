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
