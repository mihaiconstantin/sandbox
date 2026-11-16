# Imports.
from pathlib import Path

# Import the catalogue declarations and services.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.install import CatalogueInstaller
from sandbox.catalogue.loader import CatalogueLoader
from sandbox.catalogue.recipe_service import CatalogueRecipeService
from sandbox.catalogue.removal import CatalogueRemover
from sandbox.catalogue.resolved_recipe import ResolvedCatalogueRecipe
from sandbox.catalogue.sources.factory import create_source
from sandbox.catalogue.sources.source import CatalogueSource

# Import the internal configuration facade.
from sandbox.configuration.store import ConfigurationStore

# Import the registry-facing values.
from sandbox.domain.registry import CatalogueRegistration, CatalogueRemovalPlan

# Import the typed catalogue errors.
from sandbox.errors.recipes import RecipeUnresolved

# Import the SDK result values.
from sandbox.sdk.results import CatalogueInstallState, RecipeListing

# Import the shared identifier rule.
from sandbox.validation.identifiers import validate_identifier


# Expose catalogue discovery, installation, validation, and removal.
class CatalogueOperations:
    # Configuration store.
    _store: ConfigurationStore

    # Catalogue loader.
    _loader: CatalogueLoader

    # Recipe service.
    _resolver: CatalogueRecipeService

    # Create one store-bound catalogue installer.
    def _create_installer(self) -> CatalogueInstaller:
        # Return the installer bound to the current store.
        return CatalogueInstaller(self._store.home, self._store)

    # Create one store-bound catalogue remover.
    def _create_remover(self) -> CatalogueRemover:
        # Return the remover bound to the current store.
        return CatalogueRemover(self._store.home, self._store)

    # Load and validate a registered catalogue.
    def _load(self, name: str) -> Catalogue:
        # Validate the catalogue name before resolving it.
        validate_identifier(name, "catalogue")

        # Load the manifest from the registered catalogue directory.
        return self._loader.load(self._store.resolve(name))

    # Select and resolve a recipe from a loaded catalogue.
    def _resolve(self, catalogue: Catalogue, recipe: str | None) -> ResolvedCatalogueRecipe:
        # Resolve the registered catalogue directory.
        directory: Path = self._store.resolve(catalogue.name)

        # Select the effective recipe from the explicit request or catalogue default.
        effective: str = self._resolver.select(catalogue, recipe)

        # Resolve the selected recipe into its parent-first plan.
        return self._resolver.resolve(catalogue, directory, effective)

    # Bind the operations to the client-owned configuration store.
    def __init__(self, store: ConfigurationStore) -> None:
        # Retain the configuration store.
        self._store = store

        # Bind the catalogue services.
        self._loader = CatalogueLoader()
        self._resolver = CatalogueRecipeService()

    # List every registered catalogue in name order.
    def list(self) -> tuple[CatalogueRegistration, ...]:
        # Return the validated registrations.
        return self._store.registrations()

    # Report whether a catalogue is registered and present on disk.
    def inspect_installation(self, name: str) -> CatalogueInstallState:
        # Validate the catalogue name before using it in a path.
        validate_identifier(name, "catalogue")

        # Compute the canonical destination without requiring it to exist.
        destination: Path = self._store.destination(name)

        # Determine whether the catalogue is registered.
        registered: bool = self._store.registration(name) is not None

        # Determine whether the canonical directory exists or is a symlink.
        directory_present: bool = destination.exists() or destination.is_symlink()

        # Return the observed installation state.
        return CatalogueInstallState(registered = registered, directory_present = directory_present)

    # Install a catalogue and return its installed path.
    def install(self, name: str, source: str, *, which: str | None = None, force: bool = False) -> Path:
        # Validate the catalogue name before installing it.
        validate_identifier(name, "catalogue")

        # Require a string selector when one is supplied.
        if which is not None and not isinstance(which, str):
            # Throw a programming error for Python API misuse.
            raise TypeError("which must be a string or None.")

        # Require exact replacement intent.
        if type(force) is not bool:
            # Throw a programming error for Python API misuse.
            raise TypeError("force must be a Boolean.")

        # Classify the source before checking the registration.
        catalogue_source: CatalogueSource = create_source(source)

        # Install the catalogue through the store-bound installer.
        return self._create_installer().install(name, catalogue_source, which = which, force = force)

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
    def list_recipes(self, catalogue: str) -> tuple[RecipeListing, ...]:
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
        # Delegate removal planning to the catalogue service.
        return self._create_remover().plan(name)

    # Remove a catalogue by name or by its validated removal plan.
    def remove(self, target: str | CatalogueRemovalPlan) -> bool:
        # Delegate removal to the catalogue service.
        return self._create_remover().remove(target)


# Define the public API of the `sandbox.sdk.catalogues` module.
__all__: list[str] = ["CatalogueOperations"]
