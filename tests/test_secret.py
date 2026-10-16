# Imports.
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import tomlkit

# Import the configuration facade and secret helpers.
from sandbox.configuration.secrets import remove_catalogue_secrets
from sandbox.configuration.store import ConfigurationStore

# Import the secret binding value.
from sandbox.domain.registry import SecretBinding

# Import errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError


# Verify catalogue-scoped secret binding storage.
class SecretBindingTests(unittest.TestCase):
    # Create a temporary sandbox configuration and secret file.
    def make_sandbox(self) -> tuple[Path, Path]:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Prepare the sandbox directory and registry.
        home: Path = Path(temporary.name)
        (home / "catalogues.toml").write_text('[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n', encoding = "utf-8")

        # Prepare a secret file outside the catalogue tree.
        secret_file: Path = home / "keys" / "example-secret"
        secret_file.parent.mkdir()
        secret_file.write_text("secret-value\n", encoding = "utf-8")

        # Return the sandbox directory and secret file.
        return home, secret_file

    # Save, load, list, and remove a catalogue-scoped binding.
    def test_saves_loads_lists_and_removes_a_binding(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()

        # Save the binding and require the resolved path.
        saved: SecretBinding = ConfigurationStore(home).save_secret("default", "example-secret", secret_file)
        self.assertEqual(saved.host_path, secret_file.resolve())

        # Require the loaded and listed binding to match the saved path.
        self.assertEqual(ConfigurationStore(home).load_secret("default", "example-secret"), secret_file.resolve())
        self.assertEqual(ConfigurationStore(home).secret_bindings(), (SecretBinding("default", "example-secret", secret_file.resolve()),))

        # Require the catalogue registry to remain intact.
        configuration: dict[str, Any] = tomllib.loads((home / "catalogues.toml").read_text(encoding = "utf-8"))
        self.assertEqual(configuration["catalogues"]["default"]["type"], "bundled")
        self.assertEqual(configuration["secrets"]["default"]["example-secret"]["file"], str(secret_file.resolve()))

        # Remove the binding and require it to disappear.
        self.assertTrue(ConfigurationStore(home).remove_secret("default", "example-secret"))
        self.assertIsNone(ConfigurationStore(home).load_secret("default", "example-secret"))
        self.assertEqual(ConfigurationStore(home).secret_bindings(), ())

        # Require a second removal to report nothing removed.
        self.assertFalse(ConfigurationStore(home).remove_secret("default", "example-secret"))

    # Reject invalid identifiers before removing a binding.
    def test_rejects_invalid_identifiers_before_removing(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()

        # Save a valid binding first.
        ConfigurationStore(home).save_secret("default", "example-secret", secret_file)

        # Reject every invalid catalogue or alias combination.
        identifiers: tuple[tuple[str, str], ...] = (("Default", "example-secret"), ("default", "Example-Secret"))
        for catalogue, alias in identifiers:
            with self.subTest(catalogue = catalogue, alias = alias):
                # Require identifier validation to fail before storage is touched.
                with self.assertRaises(ConfigurationError):
                    ConfigurationStore(home).remove_secret(catalogue, alias)

        # Require the valid binding to remain.
        self.assertEqual(ConfigurationStore(home).load_secret("default", "example-secret"), secret_file.resolve())

    # Preserve sibling bindings when one binding is removed.
    def test_preserves_other_catalogue_bindings(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()

        # Prepare a second secret file.
        github_file: Path = home / "keys" / "github"
        github_file.write_text("github-value\n", encoding = "utf-8")

        # Save two bindings and remove one.
        ConfigurationStore(home).save_secret("default", "example-secret", secret_file)
        ConfigurationStore(home).save_secret("default", "github", github_file)
        self.assertTrue(ConfigurationStore(home).remove_secret("default", "example-secret"))

        # Require the remaining binding to survive.
        self.assertEqual(ConfigurationStore(home).secret_bindings(), (SecretBinding("default", "github", github_file.resolve()),))

    # Resolve a stored relative secret path against the sandbox directory.
    def test_loads_relative_paths_relative_to_the_sandbox(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()

        # Store the binding with a sandbox-relative path.
        (home / "catalogues.toml").write_text('[secrets.default.example-secret]\nfile = "keys/example-secret"\n', encoding = "utf-8")

        # Resolve the relative path against the sandbox directory.
        self.assertEqual(ConfigurationStore(home).load_secret("default", "example-secret"), secret_file.resolve())

    # Reject missing and directory secret paths.
    def test_rejects_missing_or_directory_secret_files(self) -> None:
        # Create a sandbox with a registered default catalogue.
        home: Path
        _secret_file: Path
        home, _secret_file = self.make_sandbox()

        # Reject a missing file.
        with self.assertRaises(ValueError):
            ConfigurationStore(home).save_secret("default", "example-secret", home / "missing")

        # Reject a directory.
        with self.assertRaises(ValueError):
            ConfigurationStore(home).save_secret("default", "example-secret", home / "keys")

        # Require no binding to have been written.
        self.assertIsNone(ConfigurationStore(home).load_secret("default", "example-secret"))

    # Reject invalid catalogue and secret identifiers when saving.
    def test_rejects_invalid_configuration_keys(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()

        # Reject an uppercase catalogue name.
        with self.assertRaises(ConfigurationError):
            ConfigurationStore(home).save_secret("Default", "example-secret", secret_file)

        # Reject an uppercase secret alias.
        with self.assertRaises(ConfigurationError):
            ConfigurationStore(home).save_secret("default", "Example-Secret", secret_file)

        # Require no binding to have been written.
        self.assertIsNone(ConfigurationStore(home).load_secret("default", "example-secret"))

    # Reject malformed `secrets` sections across every storage operation.
    def test_rejects_malformed_secret_sections(self) -> None:
        # Cover a scalar section and a scalar catalogue entry.
        configurations: tuple[str, ...] = (
            'secrets = 5\n[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n',
            '[secrets]\ndefault = "invalid"\n',
        )
        for configuration in configurations:
            with self.subTest(configuration = configuration):
                # Create a fresh sandbox with a registered catalogue and secret file.
                home: Path
                secret_file: Path
                home, secret_file = self.make_sandbox()
                (home / "catalogues.toml").write_text(configuration, encoding = "utf-8")

                # Require every operation to reject the malformed section.
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).load_secret("default", "example-secret")
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).secret_bindings()
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).remove_secret("default", "example-secret")
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).save_secret("default", "example-secret", secret_file)

    # Reject malformed individual secret bindings.
    def test_rejects_malformed_secret_bindings(self) -> None:
        # Cover a scalar binding and one without a `file` entry.
        configurations: tuple[str, ...] = (
            '[secrets.default]\nexample-secret = "invalid"\n',
            '[secrets.default.example-secret]\ntype = "invalid"\n',
        )
        for configuration in configurations:
            with self.subTest(configuration = configuration):
                # Create a fresh sandbox with a registered catalogue.
                home: Path
                _secret_file: Path
                home, _secret_file = self.make_sandbox()
                (home / "catalogues.toml").write_text(configuration, encoding = "utf-8")

                # Require reading operations to reject malformed bindings.
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).load_secret("default", "example-secret")
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).secret_bindings()

    # Reject malformed TOML in the configuration file.
    def test_rejects_invalid_toml(self) -> None:
        # Create a sandbox with a registered default catalogue.
        home: Path
        _secret_file: Path
        home, _secret_file = self.make_sandbox()
        (home / "catalogues.toml").write_text("[secrets.default\n", encoding = "utf-8")

        # Require malformed TOML to be reported as a registry error.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).load_secret("default", "example-secret")
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).secret_bindings()

    # Preserve the configuration and clean up when saving fails.
    def test_failed_save_preserves_configuration_and_removes_temporary_file(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()
        registry_file: Path = home / "catalogues.toml"
        original: str = registry_file.read_text(encoding = "utf-8")

        # Require replacement failures to leave the original configuration intact.
        with (
            mock.patch("sandbox.configuration.registry.os.replace", side_effect = OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            ConfigurationStore(home).save_secret("default", "example-secret", secret_file)

        # Require the original content, no temporary file, and no binding.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)
        self.assertEqual(list(home.glob(f".{registry_file.name}.*.tmp")), [])
        self.assertIsNone(ConfigurationStore(home).load_secret("default", "example-secret"))

    # Preserve the binding and clean up when removal fails.
    def test_failed_removal_preserves_binding_and_removes_temporary_file(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()
        registry_file: Path = home / "catalogues.toml"
        ConfigurationStore(home).save_secret("default", "example-secret", secret_file)
        original: str = registry_file.read_text(encoding = "utf-8")

        # Require replacement failures to leave the binding intact.
        with (
            mock.patch("sandbox.configuration.registry.os.replace", side_effect = OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            ConfigurationStore(home).remove_secret("default", "example-secret")

        # Require the original content, no temporary file, and the existing binding.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)
        self.assertEqual(list(home.glob(f".{registry_file.name}.*.tmp")), [])
        self.assertEqual(ConfigurationStore(home).load_secret("default", "example-secret"), secret_file.resolve())

    # Preserve unrelated registry entries and comments when saving.
    def test_preserves_unrelated_registry_entries_and_comments(self) -> None:
        # Create a sandbox with a registered default catalogue and secret file.
        home: Path
        secret_file: Path
        home, secret_file = self.make_sandbox()
        registry_file: Path = home / "catalogues.toml"
        registry_file.write_text(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n',
            encoding = "utf-8",
        )

        # Save a binding alongside the existing configuration.
        ConfigurationStore(home).save_secret("default", "example-secret", secret_file)

        # Require unrelated entries, registration, and comments to survive.
        text: str = registry_file.read_text(encoding = "utf-8")
        configuration: dict[str, Any] = tomllib.loads(text)
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"], {"value": 1})
        self.assertEqual(configuration["catalogues"]["default"]["path"], "catalogues/default")
        self.assertEqual(configuration["secrets"]["other"]["github"]["file"], "keys/github")
        self.assertEqual(configuration["secrets"]["default"]["example-secret"]["file"], str(secret_file.resolve()))

    # Treat a missing configuration file as empty for reads and fail for writes.
    def test_missing_configuration_has_no_bindings(self) -> None:
        # Create a sandbox directory without a configuration file.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name)

        # Require empty results without a configuration file.
        self.assertEqual(ConfigurationStore(home).secret_bindings(), ())
        self.assertIsNone(ConfigurationStore(home).load_secret("default", "example-secret"))
        self.assertFalse(ConfigurationStore(home).remove_secret("default", "example-secret"))

        # Require saving without a configuration file to fail with a typed error.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).save_secret("default", "example-secret", home / "missing")


# Verify removal of every binding for a catalogue.
class RemoveCatalogueSecretsTests(unittest.TestCase):
    # Create a temporary registry file with the given content.
    def make_registry(self, content: str) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Write the registry content.
        registry_file: Path = Path(temporary.name) / "catalogues.toml"
        registry_file.write_text(content, encoding = "utf-8")

        # Return the registry file path.
        return registry_file

    # Remove only the bindings of the requested catalogue.
    def test_removes_only_the_requested_catalogue_bindings(self) -> None:
        # Prepare bindings for two catalogues and unrelated content.
        registry_file: Path = self.make_registry(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[secrets.team.api_key]\nfile = "keys/api_key"\n\n'
            '[secrets.team.token]\nfile = "keys/token"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n'
        )
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove the bindings of the requested catalogue.
        remove_catalogue_secrets(registry, "team", registry_file)

        # Require the sibling bindings, comment, and unrelated table to survive.
        text: str = tomlkit.dumps(registry)
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertNotIn("team", configuration["secrets"])
        self.assertIn("other", configuration["secrets"])
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"]["value"], 1)

    # Remove the empty secret section after the last binding.
    def test_removes_the_empty_secret_section(self) -> None:
        # Prepare a registry with one catalogue binding.
        registry_file: Path = self.make_registry('[secrets.team.api_key]\nfile = "keys/api_key"\n')
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove the bindings of the only catalogue.
        remove_catalogue_secrets(registry, "team", registry_file)

        # Require the empty secret section to be removed.
        self.assertNotIn("secrets", registry)

    # Leave the registry unchanged when the catalogue has no bindings.
    def test_missing_catalogue_bindings_are_a_no_op(self) -> None:
        # Prepare bindings for another catalogue.
        registry_file: Path = self.make_registry('[secrets.other.github]\nfile = "keys/github"\n')
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove bindings for an unconfigured catalogue.
        remove_catalogue_secrets(registry, "team", registry_file)

        # Require the existing bindings to survive.
        self.assertIn("other", registry["secrets"])

    # Reject a malformed catalogue binding section.
    def test_rejects_a_malformed_binding_section(self) -> None:
        # Prepare a registry with a scalar catalogue binding section.
        registry_file: Path = self.make_registry('[secrets]\nteam = "invalid"\n')
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Require the malformed section to be reported as a domain error.
        with self.assertRaises(RegistryError):
            remove_catalogue_secrets(registry, "team", registry_file)


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
