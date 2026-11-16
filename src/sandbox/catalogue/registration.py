# Imports.
from dataclasses import replace
from pathlib import Path

# Import registry values.
from sandbox.configuration.store import ConfigurationStore
from sandbox.domain.registry import CatalogueBinding, CatalogueRegistration

# Import errors.
from sandbox.errors.catalogues import RegistryError


# Read catalogue registrations from one configuration store.
class CatalogueRegistrationReader:
    # Configuration store.
    store: ConfigurationStore

    # Initialize the reader.
    def __init__(self: "CatalogueRegistrationReader", home: Path, store: ConfigurationStore | None = None) -> None:
        # Bind and retain the configuration store.
        self.store = store if store is not None else ConfigurationStore(home.expanduser().resolve())

    # Read one registered catalogue with its secret bindings.
    def read(self: "CatalogueRegistrationReader", name: str) -> CatalogueRegistration | None:
        # Read the requested registration.
        registration: CatalogueRegistration | None = self.store.registration(name)

        # If the catalogue is not registered.
        if registration is None:
            # Return no registration.
            return None

        # Collect the catalogue-scoped secret bindings.
        bindings: tuple[CatalogueBinding, ...] = tuple(
            CatalogueBinding(binding.alias, binding.host_path)
            for binding in self.store.secret_bindings(name)
        )

        # Return the enriched registration.
        return replace(registration, bindings = bindings)

    # Validate one registration and return its canonical directory.
    def resolve_canonical_directory(self: "CatalogueRegistrationReader", registration: CatalogueRegistration) -> Path:
        # Compute the canonical catalogue directory.
        catalogue_dir: Path = self.store.destination(registration.name)

        # Resolve the catalogue directory.
        resolved_dir: Path = catalogue_dir.resolve()

        # If the catalogue directory escapes the sandbox.
        if not resolved_dir.is_relative_to(self.store.home):
            # Throw.
            raise RegistryError(f"Catalogue `{registration.name}` is not stored inside the `sandbox` directory.")

        # If the registration path is not canonical.
        if registration.path.expanduser().resolve() != resolved_dir:
            # Throw.
            raise RegistryError(f"Catalogue `{registration.name}` is registered at the noncanonical path `{registration.path}`.")

        # Return the canonical directory.
        return catalogue_dir
