# Imports.
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

# Import the catalogue declarations, loaders, sources, installer, and removal helpers.
from sandbox.catalogue import manifest, removal, sources
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.install import CatalogueInstaller
from sandbox.catalogue.resolve import ResolvedCatalogueRecipe, resolve_recipe, select_recipe

# Import the internal configuration facade and the bundled source discriminator.
from sandbox.configuration.registry import BUNDLED_CATALOGUE_TYPE
from sandbox.configuration.store import ConfigurationStore

# Import the registry-facing values.
from sandbox.domain.registry import CatalogueBinding, CatalogueRegistration, CatalogueRemovalPlan

# Import the typed catalogue errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.removal import IncompleteRemoval

# Import the shared identifier rule.
from sandbox.validation.identifiers import validate_identifier

# Import the SDK result values.
from sandbox.sdk.results import CatalogueInstallState, RecipeListing


# Define the source value that selects the bundled catalogue.
BUNDLED_CATALOGUE_SOURCE: str = BUNDLED_CATALOGUE_TYPE


# Expose catalogue discovery, installation, validation, and removal.
class CatalogueOperations:
    # Bind the operations to the client-owned configuration store.
    def __init__(self, store: ConfigurationStore) -> None:
        # Retain the configuration store.
        self._store: ConfigurationStore = store

    # List every registered catalogue in name order.
    def list(self) -> tuple[CatalogueRegistration, ...]:
        # Return the validated registrations.
        return self._store.registrations()

    # Report whether a catalogue is registered and present on disk.
    def installation(self, name: str) -> CatalogueInstallState:
        # Validate the catalogue name before using it in a path.
        validate_identifier(name, "catalogue")

        # Compute the canonical destination without requiring it to exist.
        destination: Path = self._store.destination(name)

        # Determine whether the catalogue is registered.
        registered: bool = any(item.name == name for item in self._store.registrations())

        # Determine whether the canonical directory exists or is a symlink.
        directory_present: bool = destination.exists() or destination.is_symlink()

        # Return the observed installation state.
        return CatalogueInstallState(registered = registered, directory_present = directory_present)

    # Install a catalogue and return its installed path.
    def install(self, name: str, source: str = BUNDLED_CATALOGUE_SOURCE, *, force: bool = False) -> Path:
        # Validate the catalogue name before installing it.
        validate_identifier(name, "catalogue")

        # Require exact replacement intent.
        if type(force) is not bool:
            # Throw a programming error for Python API misuse.
            raise TypeError("force must be a Boolean.")

        # Classify the source before checking the registration.
        catalogue_source: sources.CatalogueSource = sources.source_for(source)

        # Install the catalogue through the store-bound installer.
        installer: CatalogueInstaller = CatalogueInstaller(self._store.home, self._store)
        return installer.install(name, catalogue_source, force)
