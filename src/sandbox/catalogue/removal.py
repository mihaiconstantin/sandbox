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


# Load a registered catalogue with its validated secret bindings.
def load_catalogue_registration(home: Path, name: str) -> CatalogueRegistration | None:
    # Import the store lazily to keep the filesystem module importable alone.
    from sandbox.configuration.store import ConfigurationStore

    # Read the requested registration.
    store: ConfigurationStore = ConfigurationStore(home)
    registration: CatalogueRegistration | None = store.registration(name)

    # If the catalogue is not registered.
    if registration is None:
        # Return no registration.
        return None

    # Collect the catalogue-scoped secret bindings.
    bindings: tuple[CatalogueBinding, ...] = tuple(
        CatalogueBinding(binding.alias, binding.host_path)
        for binding in store.secret_bindings(name)
    )

    # Return the registration enriched with its bindings.
    return replace(registration, bindings = bindings)
