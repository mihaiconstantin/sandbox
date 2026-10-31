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


# Validate a registered catalogue and return its canonical directory.
def canonical_catalogue_directory(registration: CatalogueRegistration, home: Path) -> Path:
    # Resolve the `sandbox` and managed catalogue roots without requiring either to exist.
    sandbox_root: Path = home.expanduser().resolve()
    catalogue_root: Path = sandbox_root / registry.CATALOGUE_ROOT

    # If the managed catalogue root resolves outside the `sandbox`.
    if not catalogue_root.resolve().is_relative_to(sandbox_root):
        # Throw.
        raise RegistryError(f"Catalogue `{registration.name}` is not stored inside the `sandbox` directory.")

    # Compute the canonical catalogue directory.
    catalogue_dir: Path = catalogue_root / registration.name

    # If the registered path is not the canonical catalogue directory.
    if registration.path.expanduser().resolve() != catalogue_dir.resolve():
        # Throw.
        raise RegistryError(f"Catalogue `{registration.name}` is registered at the noncanonical path `{registration.path}`.")

    # Return the canonical catalogue directory.
    return catalogue_dir
