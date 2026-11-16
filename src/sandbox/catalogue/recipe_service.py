# Imports.
from pathlib import Path

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.compose import resolve_compose_file
from sandbox.catalogue.recipe import Recipe
from sandbox.catalogue.resolved_recipe import ResolvedCatalogueRecipe

# Import domain values.
from sandbox.domain.volume import VolumeDeclaration

# Import errors.
from sandbox.errors.configuration import ConfigurationError


# Resolve catalogue recipes through the catalogue declaration graph.
class CatalogueRecipeService:
    # Require the selected recipe to be declared.
    def _validate_selection(self: "CatalogueRecipeService", catalogue: Catalogue, name: str) -> None:
        # If the selected recipe is declared.
        if name in catalogue.recipes:
            # Return.
            return

        # List the available recipes in deterministic order.
        available: str = ", ".join(f"`{recipe_name}`" for recipe_name in sorted(catalogue.recipes))

        # Throw.
        raise ConfigurationError("recipes", f"Recipe `{name}` is not declared in the catalogue; available recipes: {available}.")

    # Build the parent-first recipe chain.
    def _build_chain(self: "CatalogueRecipeService", catalogue: Catalogue, name: str) -> list[str]:
        # Prepare the selected-first recipe chain.
        chain: list[str] = []

        # Start at the selected recipe.
        current: str | None = name

        # While a recipe remains in the chain.
        while current is not None:
            # If the chain contains a cycle.
            if current in chain:
                # Throw.
                raise ConfigurationError(f"recipes.{current}.extends", f"Recipe dependency cycle: {' -> '.join((*chain, current))}.")

            # Add the recipe to the chain.
            chain.append(current)

            # Get the current declaration.
            recipe: Recipe = catalogue.recipes[current]

            # If the recipe declares an undeclared parent.
            if recipe.extends is not None and recipe.extends not in catalogue.recipes:
                # Throw.
                raise ConfigurationError(f"recipes.{current}.extends", f"Recipe `{recipe.extends}` is not declared in the catalogue.")

            # Continue with the parent.
            current = recipe.extends

        # Reverse the chain into parent-first order.
        chain.reverse()

        # Return the chain.
        return chain

    # Merge the physical volumes across the recipe chain.
    def _merge_volumes(self: "CatalogueRecipeService", catalogue: Catalogue, chain: list[str]) -> list[VolumeDeclaration]:
        # Prepare the resolved volume table.
        volumes: dict[str, VolumeDeclaration] = {}

        # For each recipe in the parent-first chain.
        for recipe_name in chain:
            # Get the recipe declaration.
            recipe: Recipe = catalogue.recipes[recipe_name]

            # For each declared volume alias.
            for index, alias in enumerate(recipe.volumes):
                # If the alias is not declared.
                if alias not in catalogue.volumes:
                    # Throw.
                    raise ConfigurationError(f"recipes.{recipe_name}.volumes[{index}]", f"Volume `{alias}` is not declared in the catalogue.")

                # Get the physical volume declaration.
                declaration: VolumeDeclaration = catalogue.volumes[alias]

                # If the physical volume is already required.
                if declaration.name in volumes:
                    # If the declarations conflict.
                    if volumes[declaration.name] != declaration:
                        # Throw.
                        raise ConfigurationError(f"volumes.{alias}", f"Volume `{alias}` conflicts with an existing declaration for `{declaration.name}`.")

                # Otherwise.
                else:
                    # Retain the physical volume in first-appearance order.
                    volumes[declaration.name] = declaration

        # Return the merged volumes.
        return list(volumes.values())

    # Merge the secret aliases across the recipe chain.
    def _merge_secrets(self: "CatalogueRecipeService", catalogue: Catalogue, chain: list[str]) -> list[str]:
        # Prepare the resolved secret aliases.
        secrets: list[str] = []
        seen_secrets: set[str] = set()

        # For each recipe in the parent-first chain.
        for recipe_name in chain:
            # For each declared secret alias.
            for secret in catalogue.recipes[recipe_name].secrets:
                # If the secret has not been seen.
                if secret not in seen_secrets:
                    # Retain the secret in first-appearance order.
                    secrets.append(secret)
                    seen_secrets.add(secret)

        # Return the merged secrets.
        return secrets

    # Resolve every compose file in parent-first order.
    def _resolve_compose_files(self: "CatalogueRecipeService", catalogue: Catalogue, directory: Path, chain: list[str]) -> list[Path]:
        # Return the resolved compose paths.
        return [resolve_compose_file(directory, recipe_name, catalogue.recipes[recipe_name]) for recipe_name in chain]

    # Select the effective recipe from a request, default, or sole declaration.
    def select(self: "CatalogueRecipeService", catalogue: Catalogue, requested: str | None) -> str:
        # If the caller requested a recipe.
        if requested is not None:
            # Return the requested recipe for later validation.
            return requested

        # If the catalogue declares a default recipe.
        if catalogue.default_recipe is not None:
            # Return the default recipe.
            return catalogue.default_recipe

        # If the catalogue declares exactly one recipe.
        if len(catalogue.recipes) == 1:
            # Return the sole recipe.
            return next(iter(catalogue.recipes))

        # List the available recipes in deterministic order.
        available: str = ", ".join(f"`{name}`" for name in sorted(catalogue.recipes))

        # Throw.
        raise ConfigurationError(
            "catalogue.default_recipe",
            f"Catalogue `{catalogue.name}` does not declare a default recipe; pass `--recipe` with one of: {available}.",
        )

    # Resolve one selected recipe into its parent-first plan.
    def resolve(self: "CatalogueRecipeService", catalogue: Catalogue, directory: Path, name: str) -> ResolvedCatalogueRecipe:
        # Require the selected recipe to be declared.
        self._validate_selection(catalogue, name)

        # Build the parent-first recipe chain.
        chain: list[str] = self._build_chain(catalogue, name)

        # Merge the volume and secret requirements.
        volumes: list[VolumeDeclaration] = self._merge_volumes(catalogue, chain)
        secrets: list[str] = self._merge_secrets(catalogue, chain)

        # Resolve the compose files.
        compose: list[Path] = self._resolve_compose_files(catalogue, directory, chain)

        # Get the selected recipe.
        selected: Recipe = catalogue.recipes[name]

        # Return the resolved plan.
        return ResolvedCatalogueRecipe(
            name = name,
            service = selected.service,
            recipes = chain,
            compose = compose,
            volumes = volumes,
            allow_root = selected.allow_root,
            secrets = secrets,
        )
