# Imports.
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tomlkit

# Import the configuration store.
from sandbox.configuration.store import ConfigurationStore

# Import errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.secrets import SecretFileError


# Provide temporary configuration homes for store tests.
class ConfigurationStoreTestCase(unittest.TestCase):
    # Create a temporary home with the given registry content.
    def make_home(self, registry: str | None) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name).resolve()

        # Write the registry unless the test requires it to be missing.
        if registry is not None:
            (home / "catalogues.toml").write_text(registry, encoding = "utf-8")

        # Return the configuration home.
        return home

    # Create a registered catalogue directory.
    def make_catalogue(self, home: Path, name: str = "default") -> Path:
        # Create the canonical catalogue directory and a marker file.
        directory: Path = home / "catalogues" / name
        directory.mkdir(parents = True)
        (directory / "catalogue.toml").write_text("", encoding = "utf-8")

        # Return the catalogue directory.
        return directory

    # Create a readable secret file in the configuration home.
    def make_secret(self, home: Path, name: str = "example-secret") -> Path:
        # Create the secret file.
        path: Path = home / "keys" / name
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_text("secret-value\n", encoding = "utf-8")

        # Return the secret file.
        return path


# Verify registry reads, path resolution, and registration checks.
class RegistrationReadTests(ConfigurationStoreTestCase):
    # List resolved registrations in name order and resolve registered directories.
    def test_lists_resolved_registrations_and_resolves_catalogue_directories(self) -> None:
        # Register two catalogues out of name order.
        home: Path = self.make_home(
            '[catalogues.zeta]\ntype = "local"\npath = "catalogues/zeta"\n\n'
            '[catalogues.alpha]\ntype = "bundled"\npath = "catalogues/alpha"\n'
        )
        alpha_dir: Path = self.make_catalogue(home, "alpha")

        # Prepare the store.
        store: ConfigurationStore = ConfigurationStore(home)

        # Require name order and absolute resolved registration paths.
        registrations = store.registrations()
        self.assertEqual([registration.name for registration in registrations], ["alpha", "zeta"])
        self.assertEqual(registrations[0].type, "bundled")
        self.assertEqual(registrations[0].path, alpha_dir)
        self.assertEqual(registrations[1].path, home / "catalogues" / "zeta")

        # Require single registration lookup and the unregistered result.
        self.assertIsNotNone(store.registration("alpha"))
        self.assertIsNone(store.registration("missing"))

        # Require the canonical destination for a valid name.
        self.assertEqual(store.destination("alpha"), home / "catalogues" / "alpha")

        # Require the registered directory lookup.
        self.assertEqual(store.catalogue_directory("alpha"), alpha_dir)
        self.assertIsNone(store.catalogue_directory("missing"))

        # Require resolution to the existing registered directory.
        self.assertEqual(store.resolve("alpha"), alpha_dir)

    # Reject invalid destinations before using the name in a path.
    def test_rejects_an_invalid_destination_name(self) -> None:
        # Prepare a store without a registry.
        home: Path = self.make_home(None)
        store: ConfigurationStore = ConfigurationStore(home)

        # Require the shared identifier rule.
        with self.assertRaises(ConfigurationError):
            store.destination("Invalid Name")

    # Distinguish a missing registry, an unregistered catalogue, and a non-directory target.
    def test_resolution_failures_preserve_the_current_errors(self) -> None:
        # Require a missing registry to surface its path as a typed error.
        missing_home: Path = self.make_home(None)
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(missing_home).resolve("default")
        self.assertIn(str(missing_home / "catalogues.toml"), str(raised.exception))

        # Require an unregistered catalogue to be reported.
        unregistered_home: Path = self.make_home('[catalogues.other]\ntype = "bundled"\npath = "catalogues/other"\n')
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(unregistered_home).resolve("default")
        self.assertIn("Catalogue `default` is not registered", str(raised.exception))

        # Require a canonical registration that targets a file to be refused.
        file_home: Path = self.make_home('[catalogues.broken]\ntype = "bundled"\npath = "catalogues/broken"\n')
        (file_home / "catalogues").mkdir()
        (file_home / "catalogues" / "broken").write_text("not a directory\n", encoding = "utf-8")
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(file_home).resolve("broken")
        self.assertIn("does not reference a directory", str(raised.exception))

        # Require the required lookup to add the catalogue discovery hint.
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(unregistered_home).require("default")
        self.assertIn("Run `sb list catalogues`", str(raised.exception))

    # Reject every malformed registration shape while listing.
    def test_rejects_malformed_registrations(self) -> None:
        # Cover scalar sections, scalar entries, missing fields, invalid names, and malformed TOML.
        registries: tuple[str, ...] = (
            "catalogues = 5\n",
            '[catalogues]\nbroken = "catalogues/default"\n',
            '[catalogues.broken]\npath = "catalogues/default"\n',
            '[catalogues.broken]\ntype = "bundled"\n',
            '[catalogues.broken]\ntype = 5\npath = "catalogues/default"\n',
            '[catalogues.broken]\ntype = "bundled"\npath = 5\n',
            '[catalogues."Broken Name"]\ntype = "bundled"\npath = "catalogues/default"\n',
            "[catalogues.default\n",
        )
        for registry in registries:
            with self.subTest(registry = registry):
                # Require malformed data to be reported as a registry error.
                home: Path = self.make_home(registry)
                with self.assertRaises(RegistryError):
                    ConfigurationStore(home).registrations()


# Verify registration preparation, publication, and removal.
class RegistrationWriteTests(ConfigurationStoreTestCase):
    # Create a commented registry and publish the registration atomically.
    def test_register_creates_a_commented_registry_and_preserves_a_new_file_mode(self) -> None:
        # Prepare an existing empty configuration home.
        home: Path = self.make_home(None)
        store: ConfigurationStore = ConfigurationStore(home)

        # Register a catalogue.
        registration = store.register("alpha", "bundled", False)

        # Require the resolved registration value.
        self.assertEqual(registration.name, "alpha")
        self.assertEqual(registration.type, "bundled")
        self.assertEqual(registration.path, (home / "catalogues" / "alpha").resolve())

        # Require the conventional comment and registration fields.
        text: str = store.registry_file.read_text(encoding = "utf-8")
        self.assertTrue(text.startswith("# Registered development `sandbox` catalogues.\n"))
        configuration = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "bundled", "path": "catalogues/alpha"})

        # Require a new registry to use the install-compatible file mode.
        self.assertEqual(store.registry_file.stat().st_mode & 0o777, 0o644)

    # Derive a new registry mode from the process umask.
    def test_register_respects_the_process_umask(self) -> None:
        # Create a missing registry under a restrictive umask.
        home: Path = self.make_home(None)
        store: ConfigurationStore = ConfigurationStore(home)

        # Register a catalogue while the umask denies group and other access.
        with mock.patch("os.umask", return_value = 0o077):
            store.register("team", "bundled", force = False)

        # Require the umask-derived mode.
        self.assertEqual(store.registry_file.stat().st_mode & 0o777, 0o600)

    # Preserve comments, siblings, and the existing mode when registering.
    def test_register_preserves_comments_siblings_and_mode(self) -> None:
        # Prepare a restricted registry with a comment and an unrelated table.
        home: Path = self.make_home(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n'
        )
        store: ConfigurationStore = ConfigurationStore(home)
        store.registry_file.chmod(0o640)

        # Register another catalogue.
        store.register("alpha", "bundled", False)

        # Require the sibling, comment, and unrelated table to survive.
        text: str = store.registry_file.read_text(encoding = "utf-8")
        configuration = tomlkit.parse(text)
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"]["value"], 1)
        self.assertEqual(dict(configuration["catalogues"]["other"]), {"type": "local", "path": "catalogues/other"})
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "bundled", "path": "catalogues/alpha"})

        # Require the existing registry mode to survive.
        self.assertEqual(store.registry_file.stat().st_mode & 0o777, 0o640)

    # Reject a conflicting registration without changing the document.
    def test_register_rejects_conflicts_without_writing(self) -> None:
        # Cover a different origin, a different path, a noncanonical path, and an extra field.
        registrations: tuple[tuple[str, bool], ...] = (
            ('[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\n', False),
            ('[catalogues.alpha]\ntype = "bundled"\npath = "catalogues/beta"\n', False),
            ('[catalogues.alpha]\ntype = "local"\npath = "../outside/alpha"\n', True),
            ('[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\nversion = "1"\n', True),
        )
        for registry, force in registrations:
            with self.subTest(registry = registry, force = force):
                # Prepare a registry with the conflicting registration.
                home: Path = self.make_home(registry)
                store: ConfigurationStore = ConfigurationStore(home)

                # Require the conflict to be rejected and the registry to stay unchanged.
                with self.assertRaises(RegistryError):
                    store.check_registration("alpha", "bundled", force)
                with self.assertRaises(RegistryError):
                    store.register("alpha", "bundled", force)
                self.assertEqual(store.registry_file.read_text(encoding = "utf-8"), registry)

    # Update the recorded origin when replacement is forced.
    def test_register_updates_the_origin_when_forced(self) -> None:
        # Prepare a bundled registration.
        home: Path = self.make_home('[catalogues.alpha]\ntype = "bundled"\npath = "catalogues/alpha"\n')
        store: ConfigurationStore = ConfigurationStore(home)

        # Register the same catalogue from a local source with force.
        store.register("alpha", "local", True)

        # Require the origin to change while the canonical path remains.
        configuration = tomlkit.parse(store.registry_file.read_text(encoding = "utf-8"))
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})

    # Remove a registration with its bindings and clean up empty sections.
    def test_unregister_removes_the_registration_and_bindings(self) -> None:
        # Prepare two catalogues, bindings, a comment, and an unrelated table.
        home: Path = self.make_home(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[catalogues.other]\ntype = "bundled"\npath = "catalogues/other"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n'
        )
        store: ConfigurationStore = ConfigurationStore(home)

        # Remove the first catalogue.
        self.assertTrue(store.unregister("team"))

        # Require the sibling registration and binding to survive.
        configuration = tomlkit.parse(store.registry_file.read_text(encoding = "utf-8"))
        self.assertNotIn("team", configuration["catalogues"])
        self.assertIn("other", configuration["catalogues"])
        self.assertNotIn("team", configuration["secrets"])
        self.assertIn("other", configuration["secrets"])
        self.assertIn("# Preserve this comment.", store.registry_file.read_text(encoding = "utf-8"))
        self.assertEqual(configuration["custom"]["value"], 1)

        # Remove the last catalogue and require empty sections to disappear.
        self.assertTrue(store.unregister("other"))
        configuration = tomlkit.parse(store.registry_file.read_text(encoding = "utf-8"))
        self.assertNotIn("catalogues", configuration)
        self.assertNotIn("secrets", configuration)

        # Require a repeated removal to report nothing removed.
        self.assertFalse(store.unregister("other"))

    # Preserve the document and remove the temporary file when publication fails.
    def test_failed_publication_preserves_the_document_and_removes_the_temporary_file(self) -> None:
        # Prepare a registry with an existing registration.
        original: str = '[catalogues.other]\ntype = "bundled"\npath = "catalogues/other"\n'
        home: Path = self.make_home(original)
        store: ConfigurationStore = ConfigurationStore(home)

        # Require publication failures to leave the original registry intact.
        with (
            mock.patch("sandbox.configuration.registry.os.replace", side_effect = OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            store.register("alpha", "bundled", False)

        # Require the original content and no leftover temporary file.
        self.assertEqual(store.registry_file.read_text(encoding = "utf-8"), original)
        self.assertEqual(list(home.glob(f".{store.registry_file.name}.*.tmp")), [])


# Verify catalogue-scoped secret binding storage.
class SecretBindingTests(ConfigurationStoreTestCase):
    # Save, load, list, and remove a binding.
    def test_saves_loads_lists_and_removes_a_binding(self) -> None:
        # Prepare a registered catalogue and secret file.
        home: Path = self.make_home('[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n')
        secret_file: Path = self.make_secret(home)
        store: ConfigurationStore = ConfigurationStore(home)

        # Save the binding and require the resolved value.
        binding = store.save_secret("default", "example-secret", secret_file)
        self.assertEqual(binding.catalogue, "default")
        self.assertEqual(binding.alias, "example-secret")
        self.assertEqual(binding.host_path, secret_file.resolve())

        # Require the stored binding and registration to coexist.
        configuration = tomlkit.parse(store.registry_file.read_text(encoding = "utf-8"))
        self.assertEqual(configuration["secrets"]["default"]["example-secret"]["file"], str(secret_file.resolve()))
        self.assertEqual(configuration["catalogues"]["default"]["type"], "bundled")

        # Require load and list to return the saved binding.
        self.assertEqual(store.load_secret("default", "example-secret"), secret_file.resolve())
        self.assertEqual(store.secret_bindings(), (binding,))

        # Remove the binding and require the section cleanup.
        self.assertTrue(store.remove_secret("default", "example-secret"))
        self.assertIsNone(store.load_secret("default", "example-secret"))
        self.assertEqual(store.secret_bindings(), ())
        self.assertFalse(store.remove_secret("default", "example-secret"))

        # Require the registration to survive after the last binding is removed.
        configuration = tomlkit.parse(store.registry_file.read_text(encoding = "utf-8"))
        self.assertNotIn("secrets", configuration)
        self.assertIn("default", configuration["catalogues"])

    # Resolve relative binding paths against the configuration home without validating the host file.
    def test_lists_relative_bindings_and_validates_only_when_loading(self) -> None:
        # Prepare bindings for two catalogues in reverse order with missing files.
        home: Path = self.make_home(
            '[secrets.team.token]\nfile = "keys/token"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n'
        )
        store: ConfigurationStore = ConfigurationStore(home)

        # Require sorted bindings with resolved host paths but no file validation.
        bindings = store.secret_bindings()
        self.assertEqual(
            [(binding.catalogue, binding.alias, binding.host_path) for binding in bindings],
            [
                ("other", "github", (home / "keys" / "github").resolve()),
                ("team", "api_key", (home / "keys" / "api_key").resolve()),
                ("team", "token", (home / "keys" / "token").resolve()),
            ],
        )

        # Require the catalogue-scoped filter.
        self.assertEqual([binding.alias for binding in store.secret_bindings("team")], ["api_key", "token"])

        # Require a missing host file to be rejected when loading.
        with self.assertRaises(SecretFileError):
            store.load_secret("team", "token")

    # Expand a user-directory binding path.
    def test_expands_user_directory_binding_paths(self) -> None:
        # Prepare a binding that points into the user directory.
        home: Path = self.make_home('[secrets.default.example-secret]\nfile = "~/keys/example-secret"\n')

        # Point the user directory at the configuration home.
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            bindings = ConfigurationStore(home).secret_bindings()

        # Require the expanded and resolved path.
        self.assertEqual(bindings[0].host_path, home / "keys" / "example-secret")

    # Preserve unrelated entries and comments when saving a binding.
    def test_save_preserves_comments_registrations_and_sibling_bindings(self) -> None:
        # Prepare a registry with a comment, unrelated table, and sibling binding.
        home: Path = self.make_home(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n'
        )
        secret_file: Path = self.make_secret(home)
        store: ConfigurationStore = ConfigurationStore(home)

        # Save a binding alongside the existing configuration.
        store.save_secret("default", "example-secret", secret_file)

        # Require unrelated content and the sibling binding to survive.
        text: str = store.registry_file.read_text(encoding = "utf-8")
        configuration = tomlkit.parse(text)
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"]["value"], 1)
        self.assertEqual(configuration["catalogues"]["default"]["path"], "catalogues/default")
        self.assertEqual(configuration["secrets"]["other"]["github"]["file"], "keys/github")
        self.assertEqual(configuration["secrets"]["default"]["example-secret"]["file"], str(secret_file.resolve()))

    # Reject missing configuration files and invalid host files when saving.
    def test_save_requires_a_registry_and_a_regular_readable_secret_file(self) -> None:
        # Require saving without a registry file to fail with a typed error.
        home: Path = self.make_home(None)
        store: ConfigurationStore = ConfigurationStore(home)
        with self.assertRaises(RegistryError):
            store.save_secret("default", "example-secret", home / "missing")

        # Prepare a registry and require invalid host files to be rejected.
        home = self.make_home('[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n')
        store = ConfigurationStore(home)
        with self.assertRaises(SecretFileError):
            store.save_secret("default", "example-secret", home / "missing")
        with self.assertRaises(SecretFileError):
            store.save_secret("default", "example-secret", home)

        # Require no binding to have been written.
        self.assertEqual(store.secret_bindings(), ())

    # Reject invalid identifiers and malformed secret sections.
    def test_rejects_invalid_identifiers_and_malformed_sections(self) -> None:
        # Prepare a registered catalogue and secret file.
        home: Path = self.make_home('[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n')
        secret_file: Path = self.make_secret(home)
        store: ConfigurationStore = ConfigurationStore(home)

        # Reject invalid identifiers before saving.
        with self.assertRaises(ConfigurationError):
            store.save_secret("Default", "example-secret", secret_file)
        with self.assertRaises(ConfigurationError):
            store.save_secret("default", "Example-Secret", secret_file)

        # Cover a scalar section and a scalar catalogue entry.
        configurations: tuple[str, ...] = (
            'secrets = 5\n[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n',
            '[secrets]\ndefault = "invalid"\n',
        )
        for configuration in configurations:
            with self.subTest(configuration = configuration):
                # Prepare a malformed configuration.
                malformed_home: Path = self.make_home(configuration)
                malformed_store: ConfigurationStore = ConfigurationStore(malformed_home)

                # Require every secret operation to reject the malformed section.
                with self.assertRaises(RegistryError):
                    malformed_store.load_secret("default", "example-secret")
                with self.assertRaises(RegistryError):
                    malformed_store.secret_bindings()
                with self.assertRaises(RegistryError):
                    malformed_store.remove_secret("default", "example-secret")
                with self.assertRaises(RegistryError):
                    malformed_store.save_secret("default", "example-secret", secret_file)

    # Preserve the document and binding when a removal write fails.
    def test_failed_removal_preserves_the_binding_and_removes_the_temporary_file(self) -> None:
        # Prepare a saved binding and capture the original document.
        home: Path = self.make_home('[catalogues.default]\ntype = "bundled"\npath = "catalogues/default"\n')
        secret_file: Path = self.make_secret(home)
        store: ConfigurationStore = ConfigurationStore(home)
        store.save_secret("default", "example-secret", secret_file)
        original: str = store.registry_file.read_text(encoding = "utf-8")

        # Require write failures to leave the binding intact.
        with (
            mock.patch("sandbox.configuration.registry.os.replace", side_effect = OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            store.remove_secret("default", "example-secret")

        # Require the original content, no temporary file, and the existing binding.
        self.assertEqual(store.registry_file.read_text(encoding = "utf-8"), original)
        self.assertEqual(list(home.glob(f".{store.registry_file.name}.*.tmp")), [])
        self.assertEqual(store.load_secret("default", "example-secret"), secret_file.resolve())


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
