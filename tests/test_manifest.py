# Imports.
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue

# Import manifest helpers.
from catalogue_services import MANIFEST_FILENAME, load_catalogue, resolve_compose_file

# Import errors.
from sandbox.errors.configuration import ConfigurationError

# Define the manifest used by the loader tests.
MANIFEST: str = dedent("""\
    [catalogue]
    name = "default"
    version = "0.1.0"
    schema_version = 1

    [volumes.state]
    name = "example-state"
    scope = "shared"
    target = "/home/example/.state"

    [recipes.base]
    compose = "compose.yaml"
    service = "workspace"
    volumes = ["state"]

    [recipes.r]
    compose = "r/compose.yaml"
    service = "workspace"
    extends = "base"
    volumes = ["state"]
""")

# Define the independent manifest used by the loader tests.
INDEPENDENT_MANIFEST: str = dedent("""\
    [catalogue]
    name = "standalone"
    version = "0.1.0"
    schema_version = 1

    [recipes.minimal]
    compose = "minimal/compose.yaml"
    service = "development"
""")


# Verify manifest loading, path resolution, and filesystem validation.
class LoadCatalogueTests(unittest.TestCase):
    # Create a temporary catalogue directory for one test.
    def make_catalogue(self, manifest: str | None = MANIFEST, files: tuple[str, ...] = ("compose.yaml", "r/compose.yaml")) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Resolve the temporary catalogue directory.
        directory: Path = Path(temporary.name).resolve()

        # Write the manifest when the test requires one.
        if manifest is not None:
            # Write the manifest as UTF-8.
            (directory / MANIFEST_FILENAME).write_text(manifest, encoding = "utf-8")

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

    # Verify a manifest loads typed declarations and resolves compose files.
    def test_loads_typed_declarations_and_resolves_compose_files(self) -> None:
        # Create a catalogue with a shared volume and an inherited recipe.
        directory: Path = self.make_catalogue()

        # Load and validate the manifest.
        catalogue: Catalogue = load_catalogue(directory)

        # Require the typed metadata and parent declaration.
        self.assertEqual(catalogue.name, "default")
        self.assertEqual(catalogue.recipes["r"].extends, "base")

        # Require both recipes to resolve their declared compose files.
        self.assertEqual(resolve_compose_file(directory, "base", catalogue.recipes["base"]), directory / "compose.yaml")
        self.assertEqual(resolve_compose_file(directory, "r", catalogue.recipes["r"]), directory / "r" / "compose.yaml")

    # Verify a manifest loads a declared default recipe.
    def test_manifest_loads_a_default_recipe(self) -> None:
        # Declare a schema version 1 manifest with a default recipe.
        manifest: str = dedent("""\
            [catalogue]
            name = "default"
            version = "0.1.0"
            schema_version = 1
            default_recipe = "base"

            [recipes.base]
            compose = "compose.yaml"
            service = "workspace"
        """)

        # Create and load the catalogue.
        directory: Path = self.make_catalogue(manifest, files = ("compose.yaml",))
        catalogue: Catalogue = load_catalogue(directory)

        # Require the default recipe to survive manifest loading.
        self.assertEqual(catalogue.default_recipe, "base")

    # Verify a catalogue without shared volumes loads and resolves.
    def test_independent_catalogue_does_not_require_shared_volumes(self) -> None:
        # Create a catalogue whose manifest omits the volume table.
        directory: Path = self.make_catalogue(manifest = INDEPENDENT_MANIFEST, files = ("minimal/compose.yaml",))

        # Load and validate the manifest.
        catalogue: Catalogue = load_catalogue(directory)

        # Require an empty volume table and a resolved compose file.
        self.assertEqual(dict(catalogue.volumes), {})
        self.assertEqual(resolve_compose_file(directory, "minimal", catalogue.recipes["minimal"]), directory / "minimal" / "compose.yaml")

    # Verify a missing catalogue directory is reported.
    def test_missing_catalogue_directory_is_reported(self) -> None:
        # Create a valid catalogue, then load a missing sibling directory.
        directory: Path = self.make_catalogue()
        missing: Path = directory / "missing"

        # Require a missing directory to be reported as a typed configuration error.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(missing)
        self.assertIn(str(missing), str(raised.exception))

    # Verify a catalogue path must be a directory.
    def test_catalogue_path_must_be_a_directory(self) -> None:
        # Create a valid catalogue, then load one of its files.
        directory: Path = self.make_catalogue()
        regular_file: Path = directory / "compose.yaml"

        # Require a regular file to be rejected as a catalogue directory.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(regular_file)
        self.assertIn(str(regular_file), str(raised.exception))

    # Verify a missing manifest is reported.
    def test_missing_manifest_is_reported(self) -> None:
        # Create a catalogue directory without a manifest.
        directory: Path = self.make_catalogue(manifest = None)

        # Require the missing manifest path to be reported as a typed configuration error.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertIn(str(directory / MANIFEST_FILENAME), str(raised.exception))

    # Verify the manifest must be a regular file.
    def test_manifest_must_be_a_regular_file(self) -> None:
        # Create a directory at the manifest path.
        directory: Path = self.make_catalogue(manifest = None)
        (directory / MANIFEST_FILENAME).mkdir()

        # Require the manifest to be reported as a configuration error.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "")
        self.assertIn("regular file", raised.exception.message)

    # Verify invalid TOML is reported as a configuration error.
    def test_invalid_toml_is_a_configuration_error(self) -> None:
        # Write an unterminated TOML table header.
        directory: Path = self.make_catalogue(manifest = "[catalogue\n", files = ())

        # Require the manifest to be reported as invalid TOML.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "")
        self.assertIn("not valid TOML", raised.exception.message)

    # Verify the manifest must be UTF-8 encoded.
    def test_manifest_must_be_utf8_encoded(self) -> None:
        # Replace the manifest with bytes that are not UTF-8.
        directory: Path = self.make_catalogue(files = ())
        (directory / MANIFEST_FILENAME).write_bytes(b"\xff\xfe")

        # Require the encoding failure to be reported.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "")
        self.assertIn("UTF-8", raised.exception.message)

    # Verify manifest validation retains nested field locations.
    def test_manifest_validation_retains_field_locations(self) -> None:
        # Blank the first recipe service name.
        directory: Path = self.make_catalogue(manifest = MANIFEST.replace("service = \"workspace\"", "service = \"\"", 1))

        # Require the catalogue-local recipe field to be reported.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "recipes.base.service")

    # Verify a missing compose file identifies the recipe.
    def test_missing_compose_file_identifies_the_recipe(self) -> None:
        # Create a catalogue without the inherited recipe's compose file.
        directory: Path = self.make_catalogue(files = ("compose.yaml",))

        # Require the missing file to be attributed to the recipe.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "recipes.r.compose")
        self.assertIn("does not exist", raised.exception.message)

    # Verify a compose file must be a regular file.
    def test_compose_file_must_be_a_regular_file(self) -> None:
        # Create a directory at the inherited recipe's compose path.
        directory: Path = self.make_catalogue(files = ("compose.yaml",))
        (directory / "r" / "compose.yaml").mkdir(parents = True)

        # Require the non-file compose path to be attributed to the recipe.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "recipes.r.compose")
        self.assertIn("regular file", raised.exception.message)

    # Verify a compose symlink cannot escape the catalogue.
    def test_compose_symlink_must_remain_inside_the_catalogue(self) -> None:
        # Create a catalogue whose inherited recipe has no compose file.
        directory: Path = self.make_catalogue(files = ("compose.yaml",))

        # Create a compose file outside the catalogue.
        outside: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        outside_file: Path = Path(outside.name) / "compose.yaml"
        outside_file.write_text("services: {}\n", encoding = "utf-8")

        # Point the inherited recipe's compose path at the outside file.
        (directory / "r").mkdir()
        (directory / "r" / "compose.yaml").symlink_to(outside_file)

        # Require the escaped symlink to be attributed to the recipe.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "recipes.r.compose")
        self.assertIn("inside the catalogue directory", raised.exception.message)

    # Verify a compose symlink inside the catalogue resolves to its target.
    def test_compose_symlink_inside_the_catalogue_resolves_to_its_target(self) -> None:
        # Create a catalogue whose inherited recipe has no compose file.
        directory: Path = self.make_catalogue(files = ("compose.yaml",))

        # Point the inherited recipe's compose path at the base compose file.
        (directory / "r").mkdir()
        (directory / "r" / "compose.yaml").symlink_to(directory / "compose.yaml")

        # Load the catalogue through the contained symlink.
        catalogue: Catalogue = load_catalogue(directory)

        # Require the resolved target rather than the symlink path.
        self.assertEqual(resolve_compose_file(directory, "r", catalogue.recipes["r"]), directory / "compose.yaml")

    # Verify a manifest symlink cannot escape the catalogue.
    def test_manifest_symlink_must_remain_inside_the_catalogue(self) -> None:
        # Create a catalogue directory without a manifest.
        directory: Path = self.make_catalogue(manifest = None)

        # Create a valid manifest outside the catalogue.
        outside: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        outside_manifest: Path = Path(outside.name) / MANIFEST_FILENAME
        outside_manifest.write_text(MANIFEST, encoding = "utf-8")

        # Point the catalogue manifest path at the outside file.
        (directory / MANIFEST_FILENAME).symlink_to(outside_manifest)

        # Require the escaped symlink to be rejected.
        with self.assertRaises(ConfigurationError) as raised:
            load_catalogue(directory)
        self.assertEqual(raised.exception.field, "")
        self.assertIn("inside the catalogue directory", raised.exception.message)


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
