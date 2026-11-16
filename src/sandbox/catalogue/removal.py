# Imports.
import shutil
from pathlib import Path

from sandbox.catalogue.registration import CatalogueRegistrationReader

# Import registry values.
from sandbox.configuration.store import ConfigurationStore
from sandbox.domain.registry import CatalogueRemovalPlan

# Import errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.removal import IncompleteRemoval
from sandbox.validation.identifiers import validate_identifier


# Remove catalogues from one sandbox directory.
class CatalogueRemover:
    # Configuration store.
    store: ConfigurationStore

    # Registration reader.
    reader: CatalogueRegistrationReader

    # Apply one validated catalogue removal plan.
    def _remove_plan(self: "CatalogueRemover", plan: CatalogueRemovalPlan) -> None:
        # Reload the registration to detect changes since planning.
        current = self.reader.read(plan.registration.name)

        # If the catalogue is no longer registered.
        if current is None:
            # Throw.
            raise RegistryError(f"Catalogue `{plan.registration.name}` is no longer registered.")

        # If the registration changed since planning.
        if current.type != plan.registration.type or current.path != plan.registration.path:
            # Throw.
            raise RegistryError(f"Catalogue `{plan.registration.name}` changed while planning removal.")

        # Require the reloaded registration to use the canonical path.
        catalogue_dir: Path = self.reader.resolve_canonical_directory(current)

        # Remove the catalogue files before changing the registry.
        self._remove_directory(catalogue_dir, current.name)

        # Remove the registration and bindings atomically.
        try:
            # Apply the registry change.
            self.store.unregister(current.name)

        # If the registration cannot be updated.
        except OSError as error:
            # Report the partial removal.
            raise IncompleteRemoval(
                "catalogue",
                current.name,
                f"Catalogue `{current.name}` could not be fully removed because the registry `{self.store.registry_file}` could not be updated: {error}. Rerun the command to finish.",
            ) from error

    # Remove one catalogue directory with filesystem checks.
    def _remove_directory(self: "CatalogueRemover", catalogue_dir: Path, name: str) -> None:
        # If the path is a symbolic link.
        if catalogue_dir.is_symlink():
            # Throw.
            raise RegistryError(f"Catalogue `{name}` path `{catalogue_dir}` is a symbolic link.")

        # If the directory does not exist.
        if not catalogue_dir.exists():
            # Return.
            return

        # If the path is not a directory.
        if not catalogue_dir.is_dir():
            # Throw.
            raise RegistryError(f"Catalogue `{name}` path `{catalogue_dir}` is not a directory.")

        # Remove the directory.
        try:
            # Delete the catalogue files.
            shutil.rmtree(catalogue_dir)

        # If deletion fails.
        except OSError as error:
            # Throw.
            raise IncompleteRemoval(
                "catalogue",
                name,
                detail = f"Catalogue `{name}` could not be deleted from `{catalogue_dir}`: {error}. The registry was not changed; rerun the command to finish.",
            ) from error

    # Initialize the remover.
    def __init__(self: "CatalogueRemover", home: Path, store: ConfigurationStore | None = None) -> None:
        # Bind and retain the configuration store.
        self.store = store if store is not None else ConfigurationStore(home.expanduser().resolve())

        # Bind and retain the registration reader.
        self.reader = CatalogueRegistrationReader(self.store.home, self.store)

    # Plan one catalogue removal without changing anything.
    def plan(self: "CatalogueRemover", name: str) -> CatalogueRemovalPlan | None:
        # Validate the catalogue name.
        validate_identifier(name, "catalogue")

        # Read the requested registration.
        registration = self.reader.read(name)

        # If the catalogue is not registered.
        if registration is None:
            # Return no plan.
            return None

        # Return the validated plan.
        return CatalogueRemovalPlan(home = self.store.home, registration = registration)

    # Remove a catalogue by name or by a validated plan.
    def remove(self: "CatalogueRemover", target: str | CatalogueRemovalPlan) -> bool:
        # If the caller supplied a name.
        if isinstance(target, str):
            # Plan the removal.
            plan: CatalogueRemovalPlan | None = self.plan(target)

            # If the catalogue is not registered.
            if plan is None:
                # Report no removal.
                return False

        # If the caller supplied a plan.
        elif isinstance(target, CatalogueRemovalPlan):
            # Use the validated plan.
            plan = target

        # Otherwise.
        else:
            # Throw.
            raise TypeError("target must be a catalogue name or a CatalogueRemovalPlan.")

        # Apply the plan.
        self._remove_plan(plan)

        # Report the removal.
        return True
