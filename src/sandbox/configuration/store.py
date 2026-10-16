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

    # Compute the path to the owned registry document.
    @property
    def registry_file(self) -> Path:
        # Return the registry path inside the configuration home.
        return paths.registry_path(self.home)

    # Compute the canonical destination for a catalogue name.
    def destination(self, name: str) -> Path:
        # Validate the catalogue name before using it in a path.
        validate_identifier(name, "catalogue")

        # Return the catalogue destination inside the managed catalogue root.
        return self.home / paths.CATALOGUE_ROOT / name

    # List every registration in name order with resolved absolute paths.
    def registrations(self) -> tuple[CatalogueRegistration, ...]:
        # If the registry does not exist.
        if not self.registry_file.is_file():
            # Return no registrations.
            return ()

        # Parse the registry.
        document: tomlkit.TOMLDocument = registry.load_registry(self.registry_file)

        # Return the validated registrations.
        return registry.read_registrations(document, self.home, self.registry_file)

    # Read one registration by name, or report absence.
    def registration(self, name: str) -> CatalogueRegistration | None:
        # If the registry does not exist.
        if not self.registry_file.is_file():
            # Return no registration.
            return None

        # Parse the registry.
        document: tomlkit.TOMLDocument = registry.load_registry(self.registry_file)

        # Return the validated registration or its absence.
        return registry.read_registration(document, name, self.home, self.registry_file)

    # Return the registered catalogue directory when the catalogue is registered.
    def catalogue_directory(self, name: str) -> Path | None:
        # Read the registration.
        registration: CatalogueRegistration | None = self.registration(name)

        # If the catalogue is not registered.
        if registration is None:
            # Return no directory.
            return None

        # Return the resolved registered directory.
        return registration.path

    # Resolve a registered catalogue to its absolute existing directory.
    def resolve(self, name: str) -> Path:
        # If the catalogue registry does not exist.
        if not self.registry_file.is_file():
            # Throw a clean configuration error rather than a raw file error.
            raise RegistryError(f"Catalogue registry `{self.registry_file}` does not exist.")

        # Parse the catalogue registry.
        document: tomlkit.TOMLDocument = registry.load_registry(self.registry_file)

        # Read the validated registration.
        registration: CatalogueRegistration | None = registry.read_registration(document, name, self.home, self.registry_file)

        # If the requested catalogue is not registered.
        if registration is None:
            # Throw.
            raise RegistryError(f"Catalogue `{name}` is not registered in `{self.registry_file}`.")

        # If the catalogue directory does not exist.
        if not registration.path.is_dir():
            # Throw.
            raise RegistryError(f"Catalogue `{name}` does not reference a directory.")

        # Return the resolved catalogue directory.
        return registration.path

    # Resolve a registered catalogue or explain how to discover catalogues.
    def require(self, name: str) -> Path:
        # Resolve the catalogue.
        try:
            return self.resolve(name)

        # If the catalogue cannot be resolved.
        except ValueError as error:
            # Throw with the catalogue discovery hint.
            raise RegistryError(f"{error}\nRun `sb list catalogues` to see registered catalogues.") from None

    # Validate a registration without writing the document.
    def check_registration(self, name: str, origin: str, force: bool) -> None:
        # Prepare and discard the registration document.
        registry.registration_document(self.home, self.registry_file, name, origin, force)

    # Serialize a prepared registration document without writing it.
    def prepare_registration(self, name: str, origin: str, force: bool) -> str:
        # Serialize the prepared document.
        return tomlkit.dumps(registry.registration_document(self.home, self.registry_file, name, origin, force))

    # Publish a catalogue registration with one atomic write.
    def register(self, name: str, origin: str, force: bool, replace: Any = None) -> CatalogueRegistration:
        # Prepare the registration document.
        document: tomlkit.TOMLDocument = registry.registration_document(self.home, self.registry_file, name, origin, force)

        # Use the umask-derived new-file mode only when the registry does not exist.
        new_mode: int | None = None if self.registry_file.exists() else default_file_mode()

        # Publish the document atomically.
        registry.write_registry_atomic(self.registry_file, document, replace, new_mode = new_mode)

        # Return the published registration.
        return CatalogueRegistration(name, origin, (self.home / paths.CATALOGUE_ROOT / name).resolve())

    # Remove a registration and all its secret bindings with one atomic write.
    def unregister(self, name: str) -> bool:
        # If the registry does not exist.
        if not self.registry_file.is_file():
            # Return no removal.
            return False

        # Parse the registry.
        document: tomlkit.TOMLDocument = registry.load_registry(self.registry_file)

        # Track whether the document changed.
        changed: bool = False

        # Get the registered catalogues.
        catalogues: object = document.get("catalogues")

        # If a catalogue section exists.
