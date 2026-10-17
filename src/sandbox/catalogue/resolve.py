# Imports.
from dataclasses import dataclass
from pathlib import Path

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.manifest import resolve_compose_file
from sandbox.catalogue.recipe import Recipe
from sandbox.domain.volume import VolumeDeclaration

# Import errors and helpers.
from sandbox.errors.configuration import ConfigurationError


# Represent the validated execution plan for a selected recipe.
@dataclass(frozen = True)
class ResolvedCatalogueRecipe:
    name: str
    service: str
    recipes: tuple[str, ...]
    compose: tuple[Path, ...]
    volumes: tuple[VolumeDeclaration, ...]
    allow_root: bool
    secrets: tuple[str, ...] = ()
