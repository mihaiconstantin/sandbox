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


# Select the recipe to provision from an explicit request, a catalogue default, or a sole recipe.
def select_recipe(catalogue: Catalogue, requested: str | None) -> str:
    # An explicit recipe always wins so `--recipe` overrides the catalogue default.
    if requested is not None:
        # Return the requested recipe for later validation.
        return requested

    # If the catalogue declares a default recipe.
    if catalogue.default_recipe is not None:
        # Return the catalogue default.
        return catalogue.default_recipe

    # If the catalogue declares exactly one recipe.
    if len(catalogue.recipes) == 1:
        # Return the sole available recipe.
        return next(iter(catalogue.recipes))

    # List the available recipes in deterministic order.
    available: str = ", ".join(f"`{name}`" for name in sorted(catalogue.recipes))

    # Throw.
    raise ConfigurationError(
        "catalogue.default_recipe",
        f"Catalogue `{catalogue.name}` does not declare a default recipe; pass `--recipe` with one of: {available}.",
    )


# Resolve a selected recipe into ordered `docker` compose files and volume requirements.
def resolve_recipe(catalogue: Catalogue, directory: Path, name: str) -> ResolvedCatalogueRecipe:
    # If the selected recipe is not declared in the catalogue.
    if name not in catalogue.recipes:
        # List the available recipes in deterministic order.
        available: str = ", ".join(f"`{recipe_name}`" for recipe_name in sorted(catalogue.recipes))

        # Throw.
        raise ConfigurationError("recipes", f"Recipe `{name}` is not declared in the catalogue; available recipes: {available}.")

    # Follow the optional single-parent chain from the selected recipe.
    chain: list[str] = []
    current: str | None = name

    # While a recipe remains in the chain.
    while current is not None:
        # If the recipe chain contains a cycle.
        if current in chain:
            # Throw.
            raise ConfigurationError(f"recipes.{current}.extends", f"Recipe dependency cycle: {' -> '.join((*chain, current))}.")

        # Add the recipe to the selected-first chain.
        chain.append(current)

        # Get the recipe declaration.
        recipe: Recipe = catalogue.recipes[current]

        # If the recipe declares a parent.
        if recipe.extends is not None:
            # If the parent is not declared in the catalogue.
            if recipe.extends not in catalogue.recipes:
                # Throw.
                raise ConfigurationError(f"recipes.{current}.extends", f"Recipe `{recipe.extends}` is not declared in the catalogue.")

        # Continue with the parent, if any.
        current = recipe.extends

    # Reverse the chain into parent-first order.
    chain.reverse()

    # Collect volume and secret requirements across the complete recipe chain.
    volumes: dict[str, VolumeDeclaration] = {}
    secrets: list[str] = []
    seen_secrets: set[str] = set()

    # Prepare the recipe iteration target.
    recipe_name: str

    # For each recipe in the parent-first chain.
