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

    # Resolve a registered catalogue to its absolute directory.
    def locate(self, name: str) -> Path:
        # Validate the catalogue name before resolving it.
        validate_identifier(name, "catalogue")

        # Return the registered catalogue directory.
        return self._store.resolve(name)

    # Validate a registered catalogue and return no result.
    def validate(self, name: str) -> None:
        # Load the registered catalogue through the same validation rules.
        self._load(name)

    # Return the recipes of a registered catalogue in name order.
    def recipes(self, catalogue: str) -> tuple[RecipeListing, ...]:
        # Load the catalogue declarations.
        declaration: Catalogue = self._load(catalogue)

        # Return the sorted recipe listings with the default marker.
        return tuple(
            RecipeListing(name = name, is_default = name == declaration.default_recipe)
            for name in sorted(declaration.recipes)
        )

    # Resolve a registered catalogue recipe for another SDK operation.
    def resolve_recipe(self, catalogue: str, recipe: str | None) -> ResolvedCatalogueRecipe:
        # Load the registered catalogue.
        declaration: Catalogue = self._load(catalogue)

        # Require the manifest identity to match the selected registration.
        if declaration.name != catalogue:
            # Throw.
            raise RecipeUnresolved(
                "catalogue.name",
                f"Manifest name `{declaration.name}` does not match the selected catalogue `{catalogue}`.",
            )

        # Resolve the selected recipe into its parent-first form.
        return self._resolve(declaration, recipe)

    # Plan the removal of a registered catalogue without changing anything.
    def plan_removal(self, name: str) -> CatalogueRemovalPlan | None:
        # Validate the catalogue name before planning its removal.
        validate_identifier(name, "catalogue")

        # Find the registration in name order.
        registration: CatalogueRegistration | None = next(
            (item for item in self._store.registrations() if item.name == name),
            None,
        )

        # If the catalogue is not registered.
        if registration is None:
            # Return no plan.
            return None

        # Collect the catalogue-scoped secret bindings.
        bindings: tuple[CatalogueBinding, ...] = tuple(
            CatalogueBinding(binding.alias, binding.host_path)
            for binding in self._store.secret_bindings(name)
        )

        # Enrich the registration with its bindings.
        enriched: CatalogueRegistration = replace(registration, bindings = bindings)

        # Require the registered path to be canonical before planning any change.
        removal.canonical_catalogue_directory(enriched, self._store.home)

        # Return the validated plan.
        return CatalogueRemovalPlan(home = self._store.home, registration = enriched)

    # Remove a catalogue by name or by its validated removal plan.
    def remove(self, target: str | CatalogueRemovalPlan) -> bool:
        # If the caller supplied a catalogue name.
        if isinstance(target, str):
            # Validate the name and re-plan the removal.
            plan: CatalogueRemovalPlan | None = self.plan_removal(target)

            # If the catalogue is not registered.
            if plan is None:
                # Report no removal.
                return False

        # If the caller supplied a validated removal plan.
        elif isinstance(target, CatalogueRemovalPlan):
            # Use the plan as the revalidation target.
            plan = target

        # Otherwise.
        else:
            # Throw a programming error for Python API misuse.
            raise TypeError("target must be a catalogue name or a CatalogueRemovalPlan.")

        # Apply the removal plan.
        self._remove_plan(plan)

        # Report that the catalogue was removed.
        return True

    # Load and validate a registered catalogue.
    def _load(self, name: str) -> Catalogue:
        # Validate the catalogue name before resolving it.
        validate_identifier(name, "catalogue")

        # Load the manifest from the registered catalogue directory.
        return manifest.load_catalogue(self._store.resolve(name))

    # Select and resolve a recipe from a loaded catalogue.
    def _resolve(self, catalogue: Catalogue, recipe: str | None) -> ResolvedCatalogueRecipe:
        # Resolve the registered catalogue directory.
        directory: Path = self._store.resolve(catalogue.name)

        # Select the effective recipe from the explicit request or catalogue default.
        effective: str = select_recipe(catalogue, recipe)

        # Resolve the selected recipe into its parent-first plan.
        return resolve_recipe(catalogue, directory, effective)

    # Apply one validated catalogue removal plan.
    def _remove_plan(self, plan: CatalogueRemovalPlan) -> None:
        # Reload the registration to detect any change since planning.
        current: CatalogueRegistration | None = next(
            (item for item in self._store.registrations() if item.name == plan.registration.name),
            None,
        )

        # If the catalogue is no longer registered.
        if current is None:
            # Throw.
            raise RegistryError(f"Catalogue `{plan.registration.name}` is no longer registered.")

        # If the registration changed since planning.
        if current.type != plan.registration.type or current.path != plan.registration.path:
            # Throw.
            raise RegistryError(f"Catalogue `{plan.registration.name}` changed while planning removal.")

        # Require the reloaded registration to use the canonical path.
        catalogue_dir: Path = removal.canonical_catalogue_directory(current, self._store.home)

        # Remove the catalogue files before changing the registration.
        removal.remove_catalogue_directory(catalogue_dir, current.name)

        # Remove the registration and bindings atomically.
