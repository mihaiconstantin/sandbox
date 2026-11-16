# Imports.
from pathlib import Path

# Import catalogue declarations and services.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.compose import resolve_compose_file as resolve_compose_path
from sandbox.catalogue.install import CatalogueInstaller
from sandbox.catalogue.loader import CatalogueLoader
from sandbox.catalogue.manifest import CATALOGUE_MANIFEST_FILENAME
from sandbox.catalogue.recipe import Recipe
from sandbox.catalogue.recipe_service import CatalogueRecipeService
from sandbox.catalogue.registration import CatalogueRegistrationReader
from sandbox.catalogue.resolved_recipe import ResolvedCatalogueRecipe
from sandbox.catalogue.sources.factory import create_source
from sandbox.catalogue.sources.source import CatalogueSource
from sandbox.domain.registry import CatalogueRegistration

# Define the manifest filename used by the legacy test helpers.
MANIFEST_FILENAME: str = CATALOGUE_MANIFEST_FILENAME


# Load a catalogue through the loader.
def load_catalogue(directory: Path) -> Catalogue:
    # Delegate to the loader.
    return CatalogueLoader().load(directory)


# Resolve a compose file.
def resolve_compose_file(directory: Path, name: str, recipe: Recipe) -> Path:
    # Delegate to the compose resolver.
    return resolve_compose_path(directory, name, recipe)


# Select a recipe through the recipe service.
def select_recipe(catalogue: Catalogue, requested: str | None) -> str:
    # Delegate to the recipe service.
    return CatalogueRecipeService().select(catalogue, requested)


# Resolve a recipe through the recipe service.
def resolve_recipe(catalogue: Catalogue, directory: Path, name: str) -> ResolvedCatalogueRecipe:
    # Delegate to the recipe service.
    return CatalogueRecipeService().resolve(catalogue, directory, name)


# Install a catalogue through the installer.
def install_catalogue(home: Path, name: str, source: str, *, which: str | None = None, force: bool = False) -> Path:
    # Classify the source.
    catalogue_source: CatalogueSource = create_source(source)

    # Install the catalogue.
    return CatalogueInstaller(home).install(name, catalogue_source, which = which, force = force)


# Read a catalogue registration through the registration reader.
def load_catalogue_registration(home: Path, name: str) -> CatalogueRegistration | None:
    # Delegate to the registration reader.
    return CatalogueRegistrationReader(home).read(name)


# Build a catalogue source.
def source_for(value: str) -> CatalogueSource:
    # Delegate to the source factory.
    return create_source(value)
