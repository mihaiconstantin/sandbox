# Imports.
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue

# Import manifest helpers.
from sandbox.catalogue.manifest import MANIFEST_FILENAME, load_catalogue
from sandbox.catalogue.recipe import Recipe

# Import recipe resolution.
from sandbox.catalogue.resolve import ResolvedCatalogueRecipe, resolve_recipe, select_recipe

# Import errors.
from sandbox.errors.configuration import ConfigurationError

# Define the catalogue metadata shared by the resolver tests.
CATALOGUE: str = dedent("""\
    [catalogue]
    name = "default"
    version = "0.1.0"
    schema_version = 1
""")


# Verify inheritance order, cycle detection, and volume resolution.
class ResolveRecipeTests(unittest.TestCase):
    # Create a temporary catalogue directory for one test.
    def make_catalogue(self, recipes: str, volumes: str = "", files: tuple[str, ...] = ()) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Resolve the temporary catalogue directory.
        directory: Path = Path(temporary.name).resolve()

        # Write the manifest from the shared metadata, volume table, and recipes.
        (directory / MANIFEST_FILENAME).write_text(f"{CATALOGUE}\n{volumes}\n{recipes}", encoding = "utf-8")

        # Write the `docker` compose files referenced by the manifest.
        name: str
        for name in files:
            # Compute the catalogue-relative `docker` compose path.
            path: Path = directory / name

            # Create any intermediate directories.
            path.parent.mkdir(parents = True, exist_ok = True)

            # Write a placeholder `docker` compose configuration.
            path.write_text("services: {}\n", encoding = "utf-8")

        # Return the resolved catalogue directory.
        return directory

    # Verify a child resolves its parent first and shares one physical volume.
    def test_resolves_parent_first_and_shared_volume(self) -> None:
        # Declare a parent recipe and a child that extends it.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "base-service"
            volumes = ["state"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
            volumes = ["state"]
        """)

        # Declare the shared volume both recipes require.
        volumes: str = dedent("""\
            [volumes.state]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, volumes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require parent-first recipe and compose order and a single shared volume.
        self.assertEqual(resolved.name, "r")
        self.assertEqual(resolved.service, "workspace")
        self.assertEqual(resolved.recipes, ("base", "r"))
        self.assertEqual(resolved.compose, (directory / "compose.yaml", directory / "r" / "compose.yaml"))
        self.assertEqual(tuple(volume.name for volume in resolved.volumes), ("example-state",))

    # Verify an independent recipe resolves without implicit requirements.
    def test_resolves_only_the_selected_recipe(self) -> None:
        # Declare one independent recipe without requirements.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the only recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "base")

        # Require a single-recipe plan with no volumes or secrets.
        self.assertEqual(resolved.recipes, ("base",))
        self.assertEqual(resolved.compose, (directory / "compose.yaml",))
        self.assertEqual(resolved.volumes, ())
        self.assertEqual(resolved.secrets, ())

    # Verify transitive parents resolve in parent-first order.
    def test_resolves_transitive_parents_in_order(self) -> None:
        # Declare a three-recipe parent chain.
        recipes: str = dedent("""\
            [recipes.a]
            compose = "a/compose.yaml"
            service = "a-service"

            [recipes.b]
            compose = "b/compose.yaml"
            service = "b-service"
            extends = "a"

            [recipes.c]
            compose = "c/compose.yaml"
            service = "c-service"
            extends = "b"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("a/compose.yaml", "b/compose.yaml", "c/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the grandchild recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "c")

        # Require the full parent-first chain and its compose order.
        self.assertEqual(resolved.recipes, ("a", "b", "c"))
        self.assertEqual(resolved.compose, (directory / "a" / "compose.yaml", directory / "b" / "compose.yaml", directory / "c" / "compose.yaml"))

        # Require the selected recipe's service.
        self.assertEqual(resolved.service, "c-service")

    # Verify an unknown selected recipe is reported.
    def test_unknown_selected_recipe_is_reported(self) -> None:
        # Declare one available recipe.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the missing selection to be attributed to the recipe table.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "missing")
        self.assertEqual(raised.exception.field, "recipes")
        self.assertIn("`missing`", raised.exception.message)
        self.assertIn("available recipes: `base`", raised.exception.message)

    # Verify a missing parent is reported.
    def test_missing_parent_is_reported(self) -> None:
        # Declare a recipe that extends an undeclared parent.
        recipes: str = dedent("""\
            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "missing"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("r/compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the missing parent to be attributed to the child's extends field.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "r")
        self.assertEqual(raised.exception.field, "recipes.r.extends")
        self.assertIn("`missing`", raised.exception.message)

    # Verify a recipe that extends itself reports a cycle.
    def test_self_cycle_is_reported(self) -> None:
        # Declare a recipe that extends itself.
        recipes: str = dedent("""\
            [recipes.loop]
            compose = "loop/compose.yaml"
            service = "workspace"
            extends = "loop"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("loop/compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the cycle to be attributed to the recipe's extends field.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "loop")
        self.assertEqual(raised.exception.field, "recipes.loop.extends")
        self.assertIn("cycle", raised.exception.message)

    # Verify a cycle across recipes reports its path.
    def test_multi_recipe_cycle_is_reported(self) -> None:
        # Declare two recipes that extend each other.
        recipes: str = dedent("""\
            [recipes.a]
            compose = "a/compose.yaml"
            service = "workspace"
            extends = "b"

            [recipes.b]
            compose = "b/compose.yaml"
            service = "workspace"
            extends = "a"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("a/compose.yaml", "b/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the cycle to identify the complete loop.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "a")
        self.assertEqual(raised.exception.field, "recipes.a.extends")
        self.assertIn("a -> b -> a", raised.exception.message)

    # Verify a parent's volume requirement is inherited with its target.
    def test_parent_volume_is_inherited(self) -> None:
        # Declare a parent volume and a child that does not repeat it.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["state"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
        """)

        # Declare the shared volume.
        volumes: str = dedent("""\
            [volumes.state]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, volumes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require the parent's physical volume and target to be inherited.
        self.assertEqual(tuple((volume.name, volume.target) for volume in resolved.volumes), (("example-state", "/home/example/.state"),))

    # Verify the root policy comes only from the selected recipe.
    def test_root_policy_comes_from_the_selected_recipe(self) -> None:
        # Grant root permission to the parent but not to the child.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            allow_root = true

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require the child's policy rather than the parent's permission.
        self.assertFalse(resolved.allow_root)

    # Verify aliases for one physical volume are deduplicated.
    def test_aliases_for_one_physical_volume_are_deduplicated(self) -> None:
        # Require the parent's alias and a second alias for the same physical volume.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["state"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
            volumes = ["sessions"]
        """)

        # Declare both aliases for one physical volume.
        volumes: str = dedent("""\
            [volumes.state]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"

            [volumes.sessions]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, volumes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require one physical volume despite the two aliases.
        self.assertEqual(tuple(volume.name for volume in resolved.volumes), ("example-state",))

    # Verify aliases cannot change the mount destination of a shared volume.
    def test_aliases_cannot_change_a_shared_volume_target(self) -> None:
        # Select two aliases for the same physical volume.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["state", "sessions"]
        """)

        # Give those aliases different container destinations.
        volumes: str = dedent("""\
            [volumes.state]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"

            [volumes.sessions]
            name = "example-state"
            scope = "shared"
            target = "/other"
        """)

        # Load the conflicting declarations from a disposable catalogue.
        directory: Path = self.make_catalogue(recipes, volumes, files = ("compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require resolution to identify the conflicting alias rather than discard its target.
        with self.assertRaises(ConfigurationError) as raised:
            # Resolve the complete volume requirement set.
            resolve_recipe(catalogue, directory, "base")

        # Attribute the conflict to the alias that changes the destination.
        self.assertEqual(raised.exception.field, "volumes.sessions")

    # Verify volume order follows first appearance across the chain.
    def test_volume_order_follows_first_appearance(self) -> None:
        # Declare overlapping volume requirements in parent and child.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["state", "cache"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
            volumes = ["cache"]
        """)

        # Declare both physical volumes.
        volumes: str = dedent("""\
            [volumes.state]
            name = "example-state"
            scope = "shared"
            target = "/home/example/.state"

            [volumes.cache]
            name = "cache-state"
            scope = "shared"
            target = "/cache"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, volumes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require parent-first order with the repeated alias kept in place.
        self.assertEqual(tuple(volume.name for volume in resolved.volumes), ("example-state", "cache-state"))

    # Verify secret requirements are inherited and deduplicated in order.
    def test_secret_requirements_are_inherited_and_deduplicated(self) -> None:
        # Declare overlapping secret requirements in parent and child.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            secrets = ["example-secret", "shared"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
            secrets = ["github", "example-secret"]
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the selected child recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "r")

        # Require parent-first order with the repeated secret kept in place.
        self.assertEqual(resolved.secrets, ("example-secret", "shared", "github"))

    # Verify an independent recipe can require secrets without a parent.
    def test_independent_recipe_can_require_secrets(self) -> None:
        # Declare one recipe with its own secret requirement.
        recipes: str = dedent("""\
            [recipes.frontend]
            compose = "frontend/compose.yaml"
            service = "frontend"
            secrets = ["npm"]
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("frontend/compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Resolve the only recipe.
        resolved: ResolvedCatalogueRecipe = resolve_recipe(catalogue, directory, "frontend")

        # Require the independent chain and its declared secret.
        self.assertEqual(resolved.recipes, ("frontend",))
        self.assertEqual(resolved.secrets, ("npm",))

    # Verify an undeclared volume alias is reported at its recipe position.
    def test_undeclared_volume_alias_is_reported(self) -> None:
        # Require a volume alias that the catalogue does not declare.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["missing"]
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the undeclared alias to be attributed to its array position.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "base")
        self.assertEqual(raised.exception.field, "recipes.base.volumes[0]")
        self.assertIn("`missing`", raised.exception.message)

    # Verify an undeclared parent volume alias is reported at its recipe position.
    def test_undeclared_parent_volume_alias_is_reported(self) -> None:
        # Declare an inherited recipe that requires an undeclared volume alias.
        recipes: str = dedent("""\
            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
            volumes = ["missing"]

            [recipes.r]
            compose = "r/compose.yaml"
            service = "workspace"
            extends = "base"
        """)

        # Load the catalogue from a disposable directory.
        directory: Path = self.make_catalogue(recipes, files = ("compose.yaml", "r/compose.yaml"))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the inherited alias to be attributed to the parent's array position.
        with self.assertRaises(ConfigurationError) as raised:
            resolve_recipe(catalogue, directory, "r")
        self.assertEqual(raised.exception.field, "recipes.base.volumes[0]")


# Verify deterministic recipe selection from options, catalogue defaults, and sole recipes.
class SelectRecipeTests(unittest.TestCase):
    # Build a catalogue with the requested recipes and optional default.
    def make_catalogue(self, recipes: tuple[str, ...] = ("base", "r"), default_recipe: str | None = None) -> Catalogue:
        # Build one independent recipe per identifier.
        declarations: dict[str, Recipe] = {
            name: Recipe(compose = "compose.yaml", service = "workspace")
            for name in recipes
        }

        # Return the in-memory catalogue.
        return Catalogue(
            name = "default",
            version = "0.1.0",
            schema_version = 1,
            recipes = declarations,
            default_recipe = default_recipe,
        )

    # Verify an explicit recipe wins without selection-time validation.
    def test_explicit_recipe_wins_and_is_validated_later(self) -> None:
        # Select an undeclared recipe from a catalogue with a default.
        catalogue: Catalogue = self.make_catalogue(default_recipe = "base")

        # Require the requested value to pass through unchanged.
        self.assertEqual(select_recipe(catalogue, "missing"), "missing")

    # Verify an empty explicit recipe does not fall back to the default.
    def test_empty_explicit_recipe_does_not_fall_back(self) -> None:
        # Select an empty recipe from a catalogue with a default.
        catalogue: Catalogue = self.make_catalogue(default_recipe = "base")

        # Require the empty request to pass through for resolution to reject.
        self.assertEqual(select_recipe(catalogue, ""), "")

    # Verify the catalogue default is used when no recipe is requested.
    def test_catalogue_default_is_used(self) -> None:
        # Select from a catalogue that declares a default.
        catalogue: Catalogue = self.make_catalogue(default_recipe = "r")

        # Require the declared default recipe.
        self.assertEqual(select_recipe(catalogue, None), "r")

    # Verify a sole recipe is used when no default is declared.
    def test_sole_recipe_is_used_without_a_default(self) -> None:
        # Select from a catalogue with one recipe and no default.
        catalogue: Catalogue = self.make_catalogue(recipes = ("base",))

        # Require the only available recipe.
        self.assertEqual(select_recipe(catalogue, None), "base")

    # Verify an ambiguous catalogue fails with sorted choices and the remedy.
    def test_multiple_recipes_without_a_default_fail_with_choices(self) -> None:
        # Declare multiple recipes in non-sorted order without a default.
        catalogue: Catalogue = self.make_catalogue(recipes = ("zeta", "base"))

        # Require a configuration error naming the catalogue and sorted recipes.
        with self.assertRaises(ConfigurationError) as raised:
            select_recipe(catalogue, None)
        self.assertEqual(raised.exception.field, "catalogue.default_recipe")
        self.assertIn("Catalogue `default`", raised.exception.message)
        self.assertIn("does not declare a default recipe", raised.exception.message)
        self.assertIn("`base`, `zeta`", raised.exception.message)
        self.assertIn("`--recipe`", raised.exception.message)


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
