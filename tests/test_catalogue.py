# Imports.
import unittest
from typing import Any

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.recipe import Recipe
from sandbox.domain.volume import VolumeDeclaration

# Import errors.
from sandbox.errors.configuration import ConfigurationError


# Return fresh native data for a generic example.
def catalogue_configuration() -> dict[str, Any]:
    return {
        "catalogue": {"name": "default", "version": "0.1.0", "schema_version": 1},
        "recipes": {
            "base": {"compose": "compose.yaml", "service": "workspace", "volumes": ["state"]},
            "r": {"compose": "r/compose.yaml", "service": "workspace", "extends": "base", "volumes": ["state"]},
        },
        "volumes": {"state": {"name": "example-state", "scope": "shared", "target": "/home/example/.state"}},
    }


# Verify manifest structure, diagnostics, and immutable declaration ownership.
class CatalogueTests(unittest.TestCase):
    # Require the configuration to fail at the named field.
    def assert_invalid_configuration(self, configuration: object, field: str) -> None:
        # Parse the configuration and require a configuration error.
        with self.assertRaises(ConfigurationError) as raised:
            Catalogue.from_mapping(configuration)

        # Retain the field attribution used by manifest diagnostics.
        self.assertEqual(raised.exception.field, field)

    # Verify a catalogue without a base recipe or shared volumes is valid.
    def test_independent_catalogue_does_not_require_base_or_shared_volumes(self) -> None:
        # Declare a standalone catalogue with one independent recipe.
        configuration: dict[str, Any] = {
            "catalogue": {"name": "standalone", "version": "release-2026-10", "schema_version": 1},
            "recipes": {"minimal": {"compose": "minimal/compose.yaml", "service": "development"}},
        }

        # Parse the catalogue.
        catalogue: Catalogue = Catalogue.from_mapping(configuration)

        # Require no implicit base recipe, parent, volume, or root permission.
        self.assertNotIn("base", catalogue.recipes)
        self.assertIsNone(catalogue.recipes["minimal"].extends)
        self.assertEqual(catalogue.recipes["minimal"].volumes, ())
        self.assertEqual(dict(catalogue.volumes), {})
        self.assertFalse(catalogue.recipes["minimal"].allow_root)

    # Verify a recipe does not inherit its parent's root permission.
    def test_root_permission_is_not_inherited_from_parent(self) -> None:
        # Grant root permission to the base recipe.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["recipes"]["base"]["allow_root"] = True

        # Parse both recipes.
        catalogue: Catalogue = Catalogue.from_mapping(configuration)

        # Require the permission to remain local to the base recipe.
        self.assertTrue(catalogue.recipes["base"].allow_root)
        self.assertFalse(catalogue.recipes["r"].allow_root)

    # Verify the schema version rejects coercion and unsupported versions.
    def test_schema_version_rejects_coercion_and_unsupported_versions(self) -> None:
        # Include non-integer values and unsupported integer versions.
        versions: tuple[object, ...] = (True, 1.0, "1", 2, 3)

        # Check each unsupported schema version.
        version: object
        for version in versions:
            # Identify the rejected version.
            with self.subTest(version = version):
                # Replace the supported schema version.
                configuration: dict[str, Any] = catalogue_configuration()
                configuration["catalogue"]["schema_version"] = version

                # Require the schema field to report the failure.
                self.assert_invalid_configuration(configuration, "catalogue.schema_version")

    # Verify a schema version 1 catalogue stores an optional default recipe.
    def test_default_recipe_is_optional(self) -> None:
        # Declare a schema version 1 catalogue with a default recipe.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["catalogue"]["default_recipe"] = "r"

        # Parse the catalogue.
        catalogue: Catalogue = Catalogue.from_mapping(configuration)

        # Require the schema version and declared default recipe.
        self.assertEqual(catalogue.schema_version, 1)
        self.assertEqual(catalogue.default_recipe, "r")

    # Verify a schema version 1 catalogue may omit the default recipe.
    def test_omitted_default_recipe_has_no_implicit_value(self) -> None:
        # Parse a catalogue without a default recipe.
        catalogue: Catalogue = Catalogue.from_mapping(catalogue_configuration())

        # Require no implicit default recipe.
        self.assertIsNone(catalogue.default_recipe)

    # Verify the default recipe must be a nonblank string.
    def test_default_recipe_must_be_a_nonblank_string(self) -> None:
        # Include blank strings and non-string values.
        defaults: tuple[object, ...] = ("", " ", False, 1)

        # Check each invalid default recipe.
        default: object
        for default in defaults:
            # Identify the rejected value.
            with self.subTest(default = default):
                # Replace the default recipe.
                configuration: dict[str, Any] = catalogue_configuration()
                configuration["catalogue"]["default_recipe"] = default

                # Require the default recipe field to report the failure.
                self.assert_invalid_configuration(configuration, "catalogue.default_recipe")

    # Verify the default recipe must be declared in the catalogue.
    def test_default_recipe_must_be_declared(self) -> None:
        # Reference a recipe that the catalogue does not declare.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["catalogue"]["default_recipe"] = "missing"

        # Require the default recipe field and the undeclared name.
        with self.assertRaises(ConfigurationError) as raised:
            Catalogue.from_mapping(configuration)
        self.assertEqual(raised.exception.field, "catalogue.default_recipe")
        self.assertIn("`missing`", raised.exception.message)

    # Verify unknown fields are rejected at every declaration level.
    def test_unknown_fields_are_rejected_at_each_declaration_level(self) -> None:
        # Include each table that validates its own field set.
        paths: tuple[tuple[str, ...], ...] = ((), ("catalogue",), ("recipes", "r"), ("volumes", "state"))

        # Check each declaration level.
        path: tuple[str, ...]
        for path in paths:
            # Identify the declaration level.
            with self.subTest(path = path):
                # Insert an unknown field at the selected level.
                configuration: dict[str, Any] = catalogue_configuration()
                table: Any = configuration
                name: str
                for name in path:
                    table = table[name]
                table["unexpected"] = True

                # Require the unknown field to be reported with its full path.
                self.assert_invalid_configuration(configuration, ".".join((*path, "unexpected")))

    # Verify required fields have no implicit defaults.
    def test_required_fields_have_no_implicit_defaults(self) -> None:
        # Include every required field in every declaration table.
        fields: tuple[tuple[tuple[str, ...], str], ...] = (
            ((), "catalogue"),
            ((), "recipes"),
            (("catalogue",), "name"),
            (("catalogue",), "version"),
            (("catalogue",), "schema_version"),
            (("recipes", "r"), "compose"),
            (("recipes", "r"), "service"),
            (("volumes", "state"), "name"),
            (("volumes", "state"), "scope"),
            (("volumes", "state"), "target"),
        )

        # Check each required field.
        path: tuple[str, ...]
        name: str
        for path, name in fields:
            # Identify the missing field.
            with self.subTest(path = path, name = name):
                # Remove the required field.
                configuration: dict[str, Any] = catalogue_configuration()
                table: Any = configuration
                section: str
                for section in path:
                    table = table[section]
                del table[name]

                # Require the missing field to be reported at its path.
                self.assert_invalid_configuration(configuration, ".".join((*path, name)))

    # Verify arrays cannot replace declaration tables.
    def test_arrays_cannot_replace_tables(self) -> None:
        # Require the root itself to be a table.
        self.assert_invalid_configuration([], "")

        # Include the root sections and each declaration table.
        fields: tuple[tuple[tuple[str, ...], str], ...] = (
            ((), "catalogue"),
            ((), "recipes"),
            ((), "volumes"),
            (("recipes",), "r"),
            (("volumes",), "state"),
        )

        # Check each table.
        path: tuple[str, ...]
        name: str
        for path, name in fields:
            # Identify the replaced table.
            with self.subTest(path = path, name = name):
                # Replace the table with an array.
                configuration: dict[str, Any] = catalogue_configuration()
                table: Any = configuration
                section: str
                for section in path:
                    table = table[section]
                table[name] = []

                # Require the table field to report the failure.
                self.assert_invalid_configuration(configuration, ".".join((*path, name)))

    # Verify an empty recipe table is rejected.
    def test_empty_recipe_table_is_rejected(self) -> None:
        # Remove every recipe declaration.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["recipes"] = {}

        # Require the recipes table to report the failure.
        self.assert_invalid_configuration(configuration, "recipes")

    # Verify identifiers are lowercase and catalogue-local at each level.
    def test_identifier_namespaces_are_catalogue_local_and_lowercase(self) -> None:
        # Reject an uppercase catalogue name.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["catalogue"]["name"] = "Default"
        self.assert_invalid_configuration(configuration, "catalogue.name")

        # Reject a qualified recipe identifier.
        configuration = catalogue_configuration()
        configuration["recipes"]["other/base"] = configuration["recipes"].pop("base")
        self.assert_invalid_configuration(configuration, "recipes.other/base")

        # Reject an uppercase volume alias.
        configuration = catalogue_configuration()
        configuration["volumes"]["STATE"] = configuration["volumes"].pop("state")
        self.assert_invalid_configuration(configuration, "volumes.STATE")

    # Verify the metadata version is a nonblank string.
    def test_metadata_version_must_be_a_nonblank_string(self) -> None:
        # Include a blank string and a non-string value.
        versions: tuple[object, ...] = (" ", False)

        # Check each invalid version.
        version: object
        for version in versions:
            # Identify the rejected version.
            with self.subTest(version = version):
                # Replace the catalogue version.
                configuration: dict[str, Any] = catalogue_configuration()
                configuration["catalogue"]["version"] = version

                # Require the version field to report the failure.
                self.assert_invalid_configuration(configuration, "catalogue.version")

    # Verify recipe array errors retain their catalogue-local field.
    def test_recipe_array_errors_identify_the_volume_requirement(self) -> None:
        # Require a volume alias that is not a catalogue-local identifier.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["recipes"]["r"]["volumes"] = ["state", "other/catalogue"]

        # Require the failing array item to retain the recipe prefix.
        self.assert_invalid_configuration(configuration, "recipes.r.volumes[1]")

    # Verify aliases may share one physical volume declaration.
    def test_aliases_may_share_one_physical_volume_definition(self) -> None:
        # Declare a second alias for the same physical volume.
        configuration: dict[str, Any] = catalogue_configuration()
        configuration["volumes"]["sessions"] = {"name": "example-state", "scope": "shared", "target": "/home/example/.state"}
        configuration["recipes"]["r"]["volumes"] = ["state", "sessions"]

        # Parse the aliased declarations.
        catalogue: Catalogue = Catalogue.from_mapping(configuration)

        # Require both aliases to resolve to the same declaration.
        self.assertEqual(catalogue.volumes["state"], catalogue.volumes["sessions"])
        self.assertEqual(catalogue.recipes["r"].volumes, ("state", "sessions"))

    # Verify declaration fields and tables cannot be mutated.
    def test_declaration_fields_and_tables_cannot_be_mutated(self) -> None:
        # Parse a generic catalogue.
        catalogue: Catalogue = Catalogue.from_mapping(catalogue_configuration())

        # Include one immutable field on each declaration.
        declarations: tuple[tuple[object, str, object], ...] = (
            (catalogue, "name", "changed"),
            (catalogue.recipes["base"], "allow_root", True),
            (catalogue.volumes["state"], "scope", "project"),
        )

        # Require every declaration field to reject assignment.
        declaration: object
        name: str
        value: object
        for declaration, name, value in declarations:
            # Identify the declaration type.
            with self.subTest(declaration = type(declaration).__name__):
                # Attempt to replace the declaration field.
                with self.assertRaises(AttributeError):
                    setattr(declaration, name, value)

        # Require the recipe and volume tables to reject new entries.
        with self.assertRaises(TypeError):
            catalogue.recipes["new"] = catalogue.recipes["base"]  # pyright: ignore[reportIndexIssue]
        with self.assertRaises(TypeError):
            catalogue.volumes["new"] = catalogue.volumes["state"]  # pyright: ignore[reportIndexIssue]

    # Verify mutating the source array cannot invalidate a parsed recipe.
    def test_source_array_mutation_cannot_invalidate_a_recipe(self) -> None:
        # Parse the catalogue while retaining its source data.
        configuration: dict[str, Any] = catalogue_configuration()
        catalogue: Catalogue = Catalogue.from_mapping(configuration)

        # Append a duplicate alias to the caller's source array.
        configuration["recipes"]["base"]["volumes"].append("state")

        # Require the parsed tuple to remain an independent snapshot.
        self.assertEqual(catalogue.recipes["base"].volumes, ("state",))

    # Verify clearing source tables cannot remove validated declarations.
    def test_source_table_mutation_cannot_remove_validated_declarations(self) -> None:
        # Prepare typed declarations and retain their source tables.
        recipe: Recipe = Recipe(compose = "compose.yaml", service = "workspace")
        volume: VolumeDeclaration = VolumeDeclaration(name = "example-state", scope = "shared", target = "/home/example/.state")
        recipes: dict[str, Recipe] = {"base": recipe}
        volumes: dict[str, VolumeDeclaration] = {"state": volume}

        # Construct a catalogue from the mutable tables.
        catalogue: Catalogue = Catalogue(
            name = "default",
            version = "0.1.0",
            schema_version = 1,
            recipes = recipes,
            volumes = volumes,
        )

        # Clear the caller's tables after construction.
        recipes.clear()
        volumes.clear()

        # Require the catalogue to retain its own declarations.
        self.assertEqual(catalogue.recipes["base"], recipe)
        self.assertEqual(catalogue.volumes["state"], volume)

    # Verify direct construction requires typed declarations.
    def test_direct_construction_requires_typed_declarations(self) -> None:
        # Construct a catalogue with a native recipe table.
        with self.assertRaises(ConfigurationError) as raised:
            Catalogue(
                name = "default",
                version = "0.1.0",
                schema_version = 1,
                recipes = {"base": {"compose": "compose.yaml", "service": "workspace"}},  # pyright: ignore[reportArgumentType]
            )

        # Require the offending recipe entry to be attributed.
        self.assertEqual(raised.exception.field, "recipes.base")


# Verify recipe field boundaries without opening `docker` compose files.
class RecipeTests(unittest.TestCase):
    # Verify `extends` rejects multiple parents and an explicit null.
    def test_extends_rejects_multiple_parents_and_explicit_null(self) -> None:
        # Include an array parent and an explicit null parent.
        parents: tuple[object, ...] = (["base"], None)

        # Check each invalid representation of no parent.
        parent: object
        for parent in parents:
            # Identify the rejected parent value.
            with self.subTest(parent = parent):
                # Parse a recipe with the invalid parent value.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "extends": parent})

                # Require the parent field to report the failure.
                self.assertEqual(raised.exception.field, "extends")

    # Verify a parent must be a catalogue-local identifier.
    def test_parent_must_be_a_catalogue_local_identifier(self) -> None:
        # Construct a recipe with a qualified parent.
        with self.assertRaises(ConfigurationError) as raised:
            Recipe(compose = "compose.yaml", service = "workspace", extends = "other/base")

        # Require the parent field to report the failure.
        self.assertEqual(raised.exception.field, "extends")

    # Verify `allow_root` does not coerce false-like values.
    def test_root_permission_does_not_coerce_false_values(self) -> None:
        # Include an integer and a string that resemble false.
        allow_root_values: tuple[object, ...] = (0, "false")

        # Check each non-Boolean value.
        allow_root: object
        for allow_root in allow_root_values:
            # Identify the rejected value.
            with self.subTest(allow_root = allow_root):
                # Parse a recipe with the non-Boolean value.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "allow_root": allow_root})

                # Require the root permission field to report the failure.
                self.assertEqual(raised.exception.field, "allow_root")

    # Verify volume requirements must be arrays, not scalars.
    def test_volume_requirements_must_be_arrays(self) -> None:
        # Include a Boolean and a string instead of an array.
        volume_values: tuple[object, ...] = (False, "state")

        # Check each scalar value.
        volumes: object
        for volumes in volume_values:
            # Identify the rejected value.
            with self.subTest(volumes = volumes):
                # Parse a recipe with the scalar value.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "volumes": volumes})

                # Require the volume requirements field to report the failure.
                self.assertEqual(raised.exception.field, "volumes")

    # Verify duplicate volume requirements are rejected within one recipe.
    def test_duplicate_requirements_are_rejected_within_one_recipe(self) -> None:
        # Declare the same volume alias twice.
        with self.assertRaises(ConfigurationError) as raised:
            Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "volumes": ["state", "state"]})

        # Require the duplicate item to be attributed.
        self.assertEqual(raised.exception.field, "volumes[1]")

    # Verify volume requirement items are identifiers, not coerced numbers.
    def test_volume_requirement_items_must_be_identifiers(self) -> None:
        # Declare a numeric volume alias.
        with self.assertRaises(ConfigurationError) as raised:
            Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "volumes": [1]})

        # Require the failing item to be attributed.
        self.assertEqual(raised.exception.field, "volumes[0]")

    # Verify secret requirements are parsed into an immutable tuple.
    def test_secret_requirements_are_parsed_into_a_tuple(self) -> None:
        # Parse two ordered secret aliases.
        recipe: Recipe = Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "secrets": ["example-secret", "github"]})

        # Require the parsed order and tuple representation.
        self.assertEqual(recipe.secrets, ("example-secret", "github"))

    # Verify secret requirements must be arrays, not scalars.
    def test_secret_requirements_must_be_arrays(self) -> None:
        # Include a Boolean and a string instead of an array.
        secret_values: tuple[object, ...] = (False, "example-secret")

        # Check each scalar value.
        secrets: object
        for secrets in secret_values:
            # Identify the rejected value.
            with self.subTest(secrets = secrets):
                # Parse a recipe with the scalar value.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "secrets": secrets})

                # Require the secret requirements field to report the failure.
                self.assertEqual(raised.exception.field, "secrets")

    # Verify duplicate secret requirements are rejected within one recipe.
    def test_duplicate_secret_requirements_are_rejected_within_one_recipe(self) -> None:
        # Declare the same secret alias twice.
        with self.assertRaises(ConfigurationError) as raised:
            Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "secrets": ["example-secret", "example-secret"]})

        # Require the duplicate item to be attributed.
        self.assertEqual(raised.exception.field, "secrets[1]")

    # Verify secret requirement items are identifiers.
    def test_secret_requirement_items_must_be_identifiers(self) -> None:
        # Include a qualified identifier and a number.
        secret_values: tuple[object, ...] = ("Other/secret", 1)

        # Check each invalid secret alias.
        secret: object
        for secret in secret_values:
            # Identify the rejected item.
            with self.subTest(secret = secret):
                # Parse a recipe with the invalid alias.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe.from_mapping({"compose": "compose.yaml", "service": "workspace", "secrets": [secret]})

                # Require the failing item to be attributed.
                self.assertEqual(raised.exception.field, "secrets[0]")

    # Verify compose paths reject absolute, traversing, or directory paths.
    def test_compose_paths_cannot_be_absolute_traversals_or_directories(self) -> None:
        # Include absolute, traversing, Windows, directory, and NUL paths.
        paths: tuple[str, ...] = ("/compose.yaml", "../compose.yaml", "r/../compose.yaml", "C:compose.yaml", "r\\compose.yaml", ".", "r/", "compose\x00.yaml")

        # Check each unsafe compose path.
        compose: str
        for compose in paths:
            # Identify the rejected path.
            with self.subTest(compose = compose):
                # Construct a recipe with the unsafe path.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe(compose = compose, service = "workspace")

                # Require the compose field to report the failure.
                self.assertEqual(raised.exception.field, "compose")

    # Verify service names reject interpolation and whitespace.
    def test_service_names_do_not_accept_interpolation_or_whitespace(self) -> None:
        # Include an interpolated name and a name with whitespace.
        service_values: tuple[str, ...] = ("${SERVICE}", "work space")

        # Check each unsafe service name.
        service: str
        for service in service_values:
            # Identify the rejected name.
            with self.subTest(service = service):
                # Construct a recipe with the unsafe name.
                with self.assertRaises(ConfigurationError) as raised:
                    Recipe(compose = "compose.yaml", service = service)

                # Require the service field to report the failure.
                self.assertEqual(raised.exception.field, "service")

    # Verify service names retain `docker`'s case-sensitive namespace.
    def test_service_names_are_not_lowercased_recipe_identifiers(self) -> None:
        # Construct a service name with uppercase, punctuation, and digits.
        recipe: Recipe = Recipe(compose = "compose.yaml", service = "Development.Box-1")

        # Require the name to be retained without identifier normalization.
        self.assertEqual(recipe.service, "Development.Box-1")


# Verify physical volume identity and the explicitly supported sharing policy.
class VolumeDeclarationTests(unittest.TestCase):
    # Parse one volume declaration through the manifest schema.
    def parse_volume(self, volume: dict[str, object]) -> Catalogue:
        # Build a minimal catalogue around the supplied volume declaration.
        return Catalogue.from_mapping({
            "catalogue": {"name": "default", "version": "0.1.0", "schema_version": 1},
            "recipes": {"base": {"compose": "compose.yaml", "service": "workspace"}},
            "volumes": {"state": volume},
        })

    # Verify physical volume names retain `docker`'s case-sensitive namespace.
    def test_physical_names_keep_dockers_case_sensitive_namespace(self) -> None:
        # Construct a volume with uppercase and punctuation in its physical name.
        volume: VolumeDeclaration = VolumeDeclaration(name = "STATE.State-1", scope = "shared", target = "/home/example/.state")

        # Require the physical name to be retained unchanged.
        self.assertEqual(volume.name, "STATE.State-1")

    # Verify physical names reject project aliases, leading underscores, and paths.
    def test_invalid_physical_names_are_not_project_or_host_paths(self) -> None:
        # Include a one-character name, a leading underscore, and a path.
        names: tuple[str, ...] = ("r", "_state", "host/state")

        # Check each invalid physical name.
        name: str
        for name in names:
            # Identify the rejected name.
            with self.subTest(name = name):
                # Reject the invalid name in the neutral value.
                with self.assertRaises(ValueError):
                    VolumeDeclaration(name = name, scope = "shared", target = "/home/example/.state")

                # Require the manifest field attribution for the same failure.
                with self.assertRaises(ConfigurationError) as raised:
                    self.parse_volume({"name": name, "scope": "shared", "target": "/home/example/.state"})

                self.assertEqual(raised.exception.field, "volumes.state.name")

    # Verify only the explicit `shared` scope is supported.
    def test_scope_is_explicit_and_only_shared_is_supported(self) -> None:
        # Include an unsupported scope, a blank string, and a non-string value.
        scopes: tuple[object, ...] = ("project", "", False)

        # Check each unsupported scope.
        scope: object
        for scope in scopes:
            # Identify the rejected scope.
            with self.subTest(scope = scope):
                # Parse a volume declaration with the unsupported scope.
                with self.assertRaises(ConfigurationError) as raised:
                    self.parse_volume({"name": "example-state", "scope": scope, "target": "/home/example/.state"})

                # Require the scope field to report the failure.
                self.assertEqual(raised.exception.field, "volumes.state.scope")

    # Verify targets are literal absolute container paths.
    def test_targets_must_be_literal_absolute_container_paths(self) -> None:
        # Include invalid types, relative paths, traversal, and interpolated destinations.
        targets: tuple[object, ...] = (None, False, 1, "", " ", "state", "../state", "/state/../other", "C:/state", "C:\\state", "/state\\other", "/state\x00other", "/home/${USER}/.state")

        # Check each unsafe destination against an otherwise valid declaration.
        target: object
        for target in targets:
            # Identify the destination if its validation fails.
            with self.subTest(target = target):
                # Require the target field to reject the declaration.
                with self.assertRaises(ConfigurationError) as raised:
                    # Parse the supplied destination without coercion.
                    self.parse_volume({"name": "example-state", "scope": "shared", "target": target})

                # Retain the field attribution needed by manifest diagnostics.
                self.assertEqual(raised.exception.field, "volumes.state.target")


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
