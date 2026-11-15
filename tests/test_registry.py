# Imports.
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tomlkit

# Import registry helpers and the configuration facade.
from sandbox.configuration.registry import remove_registry_entry, write_registry_atomic
from sandbox.configuration.store import ConfigurationStore

# Import the registry-facing value.
from sandbox.domain.registry import CatalogueRegistration

# Import errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError


# Provide temporary sandbox directories with registry content for registry tests.
class RegistrySandboxTestCase(unittest.TestCase):
    # Create a temporary sandbox directory with the given registry content.
    def make_sandbox(self, registry: str | None) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name).resolve()

        # Write the registry unless the test requires it to be missing.
        if registry is not None:
            (home / "catalogues.toml").write_text(registry, encoding = "utf-8")

        # Return the sandbox directory.
        return home


# Verify catalogue registration resolution and malformed registrations.
class ResolveCatalogueTests(RegistrySandboxTestCase):
    # Require a registered relative path to resolve against the sandbox directory.
    def test_resolves_a_registered_catalogue_directory(self) -> None:
        # Create a sandbox with a registered default catalogue.
        home: Path = self.make_sandbox('[catalogues.default]\ntype = "local"\npath = "catalogues/default"\n')

        # Create the registered catalogue directory.
        catalogue_dir: Path = home / "catalogues" / "default"
        catalogue_dir.mkdir(parents = True)

        # Require the registered relative path resolved against the sandbox.
        self.assertEqual(ConfigurationStore(home).resolve("default"), catalogue_dir)

    # Require a missing registry to surface the missing file.
    def test_missing_registry_file_is_reported(self) -> None:
        # Create a sandbox without a registry.
        home: Path = self.make_sandbox(None)

        # Require a missing registry to be reported as a typed error.
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(home).resolve("default")
        self.assertIn(str(home / "catalogues.toml"), str(raised.exception))

    # Reject names that are absent from the registry.
    def test_unregistered_catalogue_is_rejected(self) -> None:
        # Create a sandbox registering only another catalogue.
        home: Path = self.make_sandbox('[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n')

        # Require an unregistered name to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("default")

    # Reject a registered path that is not a string.
    def test_invalid_registered_path_value_is_rejected(self) -> None:
        # Create a sandbox with a non-string registration path.
        home: Path = self.make_sandbox('[catalogues.broken]\ntype = "local"\npath = 5\n')

        # Require a non-string path to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("broken")

    # Require a registered path to point at a directory.
    def test_registered_path_must_reference_a_directory(self) -> None:
        # Create a sandbox whose registration targets a file.
        home: Path = self.make_sandbox('[catalogues.broken]\ntype = "local"\npath = "catalogues.toml"\n')

        # Require a file target to be rejected as a directory.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("broken")

    # Reject a scalar catalogue registration.
    def test_scalar_registration_is_rejected(self) -> None:
        # Create a sandbox with a scalar catalogue registration.
        home: Path = self.make_sandbox('[catalogues]\nbroken = "catalogues/default"\n')

        # Require a scalar registration to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("broken")

    # Reject a registration without a path.
    def test_missing_registered_path_is_rejected(self) -> None:
        # Create a sandbox with a registration lacking a path.
        home: Path = self.make_sandbox('[catalogues.broken]\ntype = "local"\n')

        # Require a registration without a path to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("broken")

    # Reject a registration whose directory does not exist.
    def test_missing_catalogue_directory_is_rejected(self) -> None:
        # Create a sandbox with a missing catalogue directory.
        home: Path = self.make_sandbox('[catalogues.broken]\ntype = "local"\npath = "catalogues/missing"\n')

        # Require a registration outside the directory tree to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("broken")

    # Reject a non-mapping `catalogues` section.
    def test_invalid_catalogues_section_is_rejected(self) -> None:
        # Create a sandbox with a non-mapping catalogue section.
        home: Path = self.make_sandbox("catalogues = 5\n")

        # Require a non-mapping catalogue section to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(home).resolve("default")

    # Report malformed TOML with the registry path.
    def test_invalid_toml_is_reported_with_its_path(self) -> None:
        # Create a sandbox with malformed TOML.
        home: Path = self.make_sandbox("[catalogues.default\n")

        # Require malformed TOML to be reported as a registry error.
        with self.assertRaises(RegistryError) as raised:
            ConfigurationStore(home).resolve("default")

        # Require the registry path to identify the malformed file.
        self.assertIn(str(home / "catalogues.toml"), str(raised.exception))


# Verify registered catalogue discovery.
class ListCataloguesTests(RegistrySandboxTestCase):
    # List registrations by name with their resolved types and paths.
    def test_lists_registrations_by_name_with_resolved_paths(self) -> None:
        # Declare the registrations out of name order.
        home: Path = self.make_sandbox(
            '[catalogues.zeta]\ntype = "local"\npath = "catalogues/zeta"\n\n'
            '[catalogues.alpha]\ntype = "git"\npath = "catalogues/alpha"\n'
        )

        # Require the registrations sorted by name with resolved locations.
        registrations: list[CatalogueRegistration] = list(ConfigurationStore(home).registrations())
        self.assertEqual([registration.name for registration in registrations], ["alpha", "zeta"])
        self.assertEqual(registrations[0].type, "git")
        self.assertEqual(registrations[0].path, home / "catalogues" / "alpha")
        self.assertEqual(registrations[1].type, "local")
        self.assertEqual(registrations[1].path, home / "catalogues" / "zeta")

    # Return no catalogues without a `catalogues` section.
    def test_missing_or_empty_registry_has_no_catalogues(self) -> None:
        # Cover a missing registry, an empty registry, and unrelated settings.
        registries: tuple[str | None, ...] = (None, "", '[secrets.default.example-secret]\nfile = "example-secret"\n')
        for registry in registries:
            with self.subTest(registry = registry):
                # Prepare the sandbox registry.
                home: Path = self.make_sandbox(registry)

                # Require no registrations without a catalogue section.
                self.assertEqual(list(ConfigurationStore(home).registrations()), [])

    # Reject every malformed registration shape.
    def test_rejects_malformed_registrations(self) -> None:
        # Include scalar sections, invalid fields, and malformed TOML.
        registries: tuple[str, ...] = (
            "catalogues = 5\n",
            '[catalogues]\nbroken = "catalogues/default"\n',
            '[catalogues.broken]\npath = "catalogues/default"\n',
            '[catalogues.broken]\ntype = "local"\n',
            '[catalogues.broken]\ntype = 5\npath = "catalogues/default"\n',
            '[catalogues.broken]\ntype = "local"\npath = 5\n',
            '[catalogues."Broken Name"]\ntype = "local"\npath = "catalogues/default"\n',
            "[catalogues.default\n",
        )
        for registry in registries:
            with self.subTest(registry = registry):
                # Prepare a registry with the malformed data.
                home: Path = self.make_sandbox(registry)

                # Require malformed registry data to be reported as a domain error.
                with self.assertRaises(RegistryError):
                    list(ConfigurationStore(home).registrations())


# Verify generic catalogue registration removal.
class RemoveCatalogueRegistrationTests(RegistrySandboxTestCase):
    # Remove one registration while preserving siblings, comments, and unrelated tables.
    def test_removes_only_the_requested_catalogue(self) -> None:
        # Prepare a registry with two catalogues and unrelated content.
        home: Path = self.make_sandbox(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\n\n'
            '[catalogues.zeta]\ntype = "local"\npath = "catalogues/zeta"\n'
        )
        registry_file: Path = home / "catalogues.toml"
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove the requested registration.
        remove_registry_entry(registry, "catalogues", "alpha", registry_file)

        # Require the sibling, comment, and unrelated table to survive.
        text: str = tomlkit.dumps(registry)
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertNotIn("alpha", configuration["catalogues"])
        self.assertIn("zeta", configuration["catalogues"])
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"]["value"], 1)

    # Remove the empty catalogue section after the last registration.
    def test_removes_the_empty_catalogue_section(self) -> None:
        # Prepare a registry with one catalogue.
        home: Path = self.make_sandbox('[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\n')
        registry_file: Path = home / "catalogues.toml"
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove the only registration.
        remove_registry_entry(registry, "catalogues", "alpha", registry_file)

        # Require the empty catalogue section to be removed.
        self.assertNotIn("catalogues", registry)

    # Leave the registry unchanged when the catalogue is absent.
    def test_missing_catalogue_is_a_no_op(self) -> None:
        # Prepare a registry with one catalogue.
        home: Path = self.make_sandbox('[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\n')
        registry_file: Path = home / "catalogues.toml"
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Remove an unregistered catalogue.
        remove_registry_entry(registry, "catalogues", "missing", registry_file)

        # Require the existing registration to survive.
        self.assertIn("alpha", registry["catalogues"])

    # Reject a non-mapping catalogue section.
    def test_rejects_a_malformed_catalogue_section(self) -> None:
        # Prepare a registry with a scalar catalogue section.
        home: Path = self.make_sandbox("catalogues = 5\n")
        registry_file: Path = home / "catalogues.toml"
        registry: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))

        # Require the malformed section to be reported as a domain error.
        with self.assertRaises(RegistryError):
            remove_registry_entry(registry, "catalogues", "alpha", registry_file)


# Provide temporary catalogue registry files for preparation tests.
class PrepareRegistryTestCase(unittest.TestCase):
    # Create a temporary registry file path.
    def make_registry(self) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Return the registry file path.
        return Path(temporary.name) / "catalogues.toml"


# Verify malformed catalogue registration preparation is rejected.
class PrepareMalformedCatalogueRegistryTests(PrepareRegistryTestCase):
    # Reject scalar and incomplete registrations.
    def test_malformed_registration_is_rejected(self) -> None:
        # Cover a scalar registration and one without a path.
        registries: tuple[str, ...] = ('[catalogues]\ndefault = "catalogues/default"\n', '[catalogues.default]\ntype = "local"\n')
        for registry in registries:
            with self.subTest(registry = registry):
                # Prepare a registry with the malformed registration.
                registry_file: Path = self.make_registry()
                registry_file.write_text(registry, encoding = "utf-8")

                # Require a scalar or incomplete registration to be rejected.
                with self.assertRaises(RegistryError):
                    ConfigurationStore(registry_file.parent).prepare_registration("default", "local", False)

    # Reject malformed TOML.
    def test_invalid_toml_is_rejected(self) -> None:
        # Prepare a registry with malformed TOML.
        registry_file: Path = self.make_registry()
        registry_file.write_text("[catalogues.default\n", encoding = "utf-8")

        # Require malformed TOML to be reported as a registry error.
        with self.assertRaises(RegistryError):
            ConfigurationStore(registry_file.parent).prepare_registration("default", "local", False)


# Verify generic catalogue registration preparation.
class PrepareCatalogueRegistryTests(PrepareRegistryTestCase):
    # Create the registry document when it is missing.
    def test_creates_a_registry_document_when_missing(self) -> None:
        # Prepare a registry path without a file.
        registry_file: Path = self.make_registry()

        # Register a local catalogue under an arbitrary name.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)

        # Require the conventional comment and the requested registration.
        self.assertTrue(text.startswith("# Registered development `sandbox` catalogues.\n"))
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})

    # Register an arbitrary name without removing other entries or comments.
    def test_registers_an_arbitrary_name_and_preserves_the_registry(self) -> None:
        # Prepare a registry with an existing catalogue and comment.
        registry_file: Path = self.make_registry()
        registry_file.write_text(
            '# Existing comment.\n[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n',
            encoding = "utf-8",
        )

        # Register a local catalogue under a non-default name.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("team-alpha", "local", False)

        # Require the requested registration, the unchanged sibling, and the comment.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["team-alpha"]), {"type": "local", "path": "catalogues/team-alpha"})
        self.assertEqual(dict(configuration["catalogues"]["other"]), {"type": "local", "path": "catalogues/other"})
        self.assertIn("# Existing comment.", text)

    # Separate a new registration from following top-level tables.
    def test_separates_a_new_registration_from_following_tables(self) -> None:
        # Prepare a registry with a catalogue and a following secret table.
        registry_file: Path = self.make_registry()
        registry_file.write_text(
            '# Registered development `sandbox` catalogues.\n\n'
            '[catalogues.default]\ntype = "local"\npath = "catalogues/default"\n\n'
            '[secrets.default.openai]\nfile = "/keys/openai"\n',
            encoding = "utf-8",
        )

        # Register another local catalogue.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("default2", "local", False)

        # Require a blank line between the new registration and the secret table.
        self.assertIn('path = "catalogues/default2"\n\n[secrets.default.openai]', text)

    # Leave an already correct generic registration unchanged and unique.
    def test_repeated_preparation_is_idempotent(self) -> None:
        # Prepare a registry without a catalogue section.
        registry_file: Path = self.make_registry()
        registry_file.write_text("# Catalogues.\n", encoding = "utf-8")

        # Prepare the same registration twice.
        first: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)
        registry_file.write_text(first, encoding = "utf-8")
        second: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)

        # Require the registration to appear exactly once and the document to remain stable.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(second)
        self.assertEqual(list(configuration["catalogues"]), ["alpha"])
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})
        self.assertEqual(second, first)

    # Reject registrations that differ from the expected local shape.
    def test_conflicting_registration_is_rejected_without_changing_the_document(self) -> None:
        # Cover a different type, a different path, and an extra key.
        registrations: tuple[str, ...] = (
            '[catalogues.alpha]\ntype = "git"\npath = "catalogues/alpha"\n',
            '[catalogues.alpha]\ntype = "local"\npath = "catalogues/beta"\n',
            '[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\nversion = "1"\n',
        )
        for registry in registrations:
            with self.subTest(registry = registry):
                # Prepare a registry with the conflicting registration.
                registry_file: Path = self.make_registry()
                registry_file.write_text(registry, encoding = "utf-8")

                # Require the conflict to be rejected and the registry to stay unchanged.
                with self.assertRaises(RegistryError):
                    ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)
                self.assertEqual(registry_file.read_text(encoding = "utf-8"), registry)

    # Update the recorded origin when replacement is forced.
    def test_force_updates_the_origin(self) -> None:
        # Prepare a registry with a different origin.
        registry_file: Path = self.make_registry()
        registry_file.write_text('[catalogues.alpha]\ntype = "git"\npath = "catalogues/alpha"\n', encoding = "utf-8")

        # Prepare the registration for a local source with force.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", True)

        # Require the origin to change while the canonical path remains.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})

    # Normalize a canonical registered path without changing its origin.
    def test_normalizes_a_canonical_registered_path(self) -> None:
        # Prepare a registry with a non-normalized but canonical path.
        registry_file: Path = self.make_registry()
        registry_file.write_text('[catalogues.alpha]\ntype = "local"\npath = "./catalogues/alpha"\n', encoding = "utf-8")

        # Prepare the same registration without force.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)

        # Require the stored path to be normalized.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})

    # Accept an absolute path that resolves to the canonical catalogue path.
    def test_accepts_an_absolute_canonical_registered_path(self) -> None:
        # Prepare a registry with an absolute canonical path.
        registry_file: Path = self.make_registry()
        absolute_path: Path = (registry_file.parent / "catalogues" / "alpha").resolve()
        registry_file.write_text(f'[catalogues.alpha]\ntype = "local"\npath = "{absolute_path}"\n', encoding = "utf-8")

        # Prepare the same registration without force.
        text: str = ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)

        # Require the stored path to be normalized.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(text)
        self.assertEqual(dict(configuration["catalogues"]["alpha"]), {"type": "local", "path": "catalogues/alpha"})

    # Reject noncanonical paths and extra fields even when replacement is forced.
    def test_force_rejects_noncanonical_paths_and_extra_fields(self) -> None:
        # Cover a noncanonical path, a sibling path, and an extra field.
        registrations: tuple[str, ...] = (
            '[catalogues.alpha]\ntype = "local"\npath = "../outside/alpha"\n',
            '[catalogues.alpha]\ntype = "local"\npath = "catalogues/beta"\n',
            '[catalogues.alpha]\ntype = "local"\npath = "catalogues/alpha"\nversion = "1"\n',
        )
        for registry in registrations:
            with self.subTest(registry = registry):
                # Prepare a registry with the conflicting registration.
                registry_file: Path = self.make_registry()
                registry_file.write_text(registry, encoding = "utf-8")

                # Require the conflict to be rejected despite force and the registry to stay unchanged.
                with self.assertRaises(RegistryError):
                    ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", True)
                self.assertEqual(registry_file.read_text(encoding = "utf-8"), registry)

    # Reject invalid names before touching the registry.
    def test_invalid_name_is_rejected_without_changing_the_document(self) -> None:
        # Prepare a registry with an existing registration.
        registry_file: Path = self.make_registry()
        original: str = '[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n'
        registry_file.write_text(original, encoding = "utf-8")

        # Require an invalid name to be rejected as a configuration error.
        with self.assertRaises(ConfigurationError):
            ConfigurationStore(registry_file.parent).prepare_registration("Not Valid", "local", False)

        # Require the registry to remain unchanged.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)

    # Reject a non-mapping `catalogues` section.
    def test_invalid_catalogues_section_is_rejected(self) -> None:
        # Prepare a registry with a scalar catalogue section.
        registry_file: Path = self.make_registry()
        registry_file.write_text("catalogues = 5\n", encoding = "utf-8")

        # Require a non-mapping catalogue section to be rejected.
        with self.assertRaises(RegistryError):
            ConfigurationStore(registry_file.parent).prepare_registration("alpha", "local", False)


# Verify atomic registry replacement.
class WriteRegistryAtomicTests(unittest.TestCase):
    # Create a temporary registry file with existing content and permissions.
    def make_registry(self) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        # Prepare the registry file.
        registry_file: Path = Path(temporary.name) / "catalogues.toml"
        registry_file.write_text('[catalogues.default]\ntype = "local"\npath = "catalogues/default"\n', encoding = "utf-8")
        registry_file.chmod(0o640)

        # Return the registry file path.
        return registry_file

    # Replace the registry while preserving its file mode.
    def test_replaces_the_registry_and_preserves_its_mode(self) -> None:
        # Prepare the replacement registry.
        registry_file: Path = self.make_registry()
        registry: tomlkit.TOMLDocument = tomlkit.parse('[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n')

        # Replace the registry atomically.
        write_registry_atomic(registry_file, registry)

        # Require the replacement content and the existing permissions.
        configuration: tomlkit.TOMLDocument = tomlkit.parse(registry_file.read_text(encoding = "utf-8"))
        self.assertIn("other", configuration["catalogues"])
        self.assertNotIn("default", configuration["catalogues"])
        self.assertEqual(registry_file.stat().st_mode & 0o777, 0o640)

    # Preserve the registry and remove the temporary file when replacement fails.
    def test_failed_replacement_preserves_the_registry_and_removes_the_temporary_file(self) -> None:
        # Prepare the replacement registry and capture the original content.
        registry_file: Path = self.make_registry()
        original: str = registry_file.read_text(encoding = "utf-8")
        registry: tomlkit.TOMLDocument = tomlkit.parse('[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n')

        # Require replacement failures to leave the original registry intact.
        with (
            mock.patch("sandbox.configuration.registry.os.replace", side_effect = OSError("replace failed")),
            self.assertRaises(OSError),
        ):
            write_registry_atomic(registry_file, registry)

        # Require the original content and no leftover temporary file.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)
        self.assertEqual(list(registry_file.parent.glob(f".{registry_file.name}.*.tmp")), [])


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
