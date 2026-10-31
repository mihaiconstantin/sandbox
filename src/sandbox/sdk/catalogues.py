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
