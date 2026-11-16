# Imports.
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

# Import SDK and configuration helpers.
from catalogue_services import load_catalogue_registration
from sandbox.domain.registry import CatalogueBinding, CatalogueRegistration, CatalogueRemovalPlan

# Import errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.removal import IncompleteRemoval

# Import the SDK client fixture.
from sdk_fixtures import make_client


# Plan a catalogue removal through the SDK.
def plan_catalogue_removal(home: Path, name: str) -> CatalogueRemovalPlan | None:
    # Delegate to the SDK.
    return make_client(home).catalogues.plan_removal(name)


# Remove a planned catalogue through the SDK.
def remove_catalogue(plan: CatalogueRemovalPlan) -> None:
    # Delegate to the SDK.
    make_client(plan.home).catalogues.remove(plan)


# Provide temporary sandbox directories with registry content for removal tests.
class CatalogueRemovalTestCase(unittest.TestCase):
    # Create a temporary sandbox directory with the given registry content.
    def make_sandbox(self, registry: str) -> Path:
        # Create a temporary directory that is removed after the test.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name).resolve()

        # Write the registry content.
        (home / "catalogues.toml").write_text(registry, encoding = "utf-8")

        # Return the sandbox directory.
        return home


# Verify removal registrations include their validated secret bindings.
class LoadCatalogueRegistrationTests(CatalogueRemovalTestCase):
    # Load a non-default catalogue with only its own bindings.
    def test_loads_a_non_default_catalogue_with_its_bindings(self) -> None:
        # Prepare a registry with two catalogues and bindings.
        home: Path = self.make_sandbox(
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n\n'
            '[secrets.other.token]\nfile = "keys/token"\n'
        )

        # Load the requested catalogue.
        registration: CatalogueRegistration | None = load_catalogue_registration(home, "team")

        # Require the registration identity and location.
        self.assertIsNotNone(registration)
        if registration is None:
            self.fail("Expected the registered catalogue to load.")
        self.assertEqual(registration.name, "team")
        self.assertEqual(registration.type, "local")
        self.assertEqual(registration.path, home / "catalogues" / "team")

        # Require only the catalogue-scoped binding.
        self.assertEqual(
            registration.bindings,
            (CatalogueBinding("api_key", (home / "keys" / "api_key").resolve()),),
        )

    # Load a registered catalogue without secret bindings.
    def test_loads_a_catalogue_without_bindings(self) -> None:
        # Prepare a registry without secret bindings.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')

        # Load the requested catalogue.
        registration: CatalogueRegistration | None = load_catalogue_registration(home, "team")

        # Require an empty binding tuple.
        self.assertIsNotNone(registration)
        if registration is None:
            self.fail("Expected the registered catalogue to load.")
        self.assertEqual(registration.bindings, ())

    # Return no registration for an unregistered catalogue.
    def test_returns_none_for_an_unregistered_catalogue(self) -> None:
        # Prepare a registry with a different catalogue.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')

        # Require an unregistered catalogue to return nothing.
        self.assertIsNone(load_catalogue_registration(home, "missing"))

    # Reject a malformed registration.
    def test_rejects_a_malformed_registration(self) -> None:
        # Prepare a registry with a scalar registration.
        home: Path = self.make_sandbox('[catalogues]\nbroken = "invalid"\n')

        # Require the malformed registration to surface as a domain error.
        with self.assertRaises(RegistryError):
            load_catalogue_registration(home, "broken")


# Verify removal planning requires a canonical sandbox-managed path.
class PlanCatalogueRemovalTests(CatalogueRemovalTestCase):
    # Plan a local catalogue with its bindings.
    def test_plans_a_local_catalogue_with_bindings(self) -> None:
        # Prepare a registry and catalogue directory for a local catalogue.
        home: Path = self.make_sandbox(
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n'
        )
        (home / "catalogues" / "team").mkdir(parents = True)

        # Plan the catalogue removal.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")

        # Require the registration and bindings.
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")
        self.assertEqual(plan.home, home)
        self.assertEqual(plan.registration.name, "team")
        self.assertEqual(plan.registration.type, "local")
        self.assertEqual(plan.registration.path, home / "catalogues" / "team")
        self.assertEqual(
            plan.registration.bindings,
            (CatalogueBinding("api_key", (home / "keys" / "api_key").resolve()),),
        )

    # Return no plan for an unregistered catalogue.
    def test_returns_none_for_an_unregistered_catalogue(self) -> None:
        # Prepare a registry with a different catalogue.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')

        # Require an unregistered catalogue to produce no plan.
        self.assertIsNone(plan_catalogue_removal(home, "missing"))

    # Reject a registration outside the managed catalogue root.
    def test_rejects_a_noncanonical_registration(self) -> None:
        # Prepare a registry whose registration points outside the managed root.
        home: Path = self.make_sandbox('[catalogues.vendor]\ntype = "local"\npath = "external/vendor"\n')

        # Require the noncanonical registration to be refused before any change.
        with self.assertRaises(RegistryError):
            plan_catalogue_removal(home, "vendor")

    # Reject a registration that targets another catalogue.
    def test_rejects_a_sibling_catalogue_path(self) -> None:
        # Prepare a registry whose registration targets a sibling catalogue.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/other"\n')

        # Require the mismatched registration to be refused.
        with self.assertRaises(RegistryError):
            plan_catalogue_removal(home, "team")

    # Reject a managed root that resolves outside the sandbox.
    def test_rejects_a_managed_root_that_resolves_outside_the_sandbox(self) -> None:
        # Prepare an empty sandbox and an external directory.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        external_dir: Path = Path(temporary.name).resolve()

        # Link the managed root to the external directory.
        (home / "catalogues").symlink_to(external_dir, target_is_directory = True)

        # Require planning to be refused for the escaped root.
        with self.assertRaises(RegistryError):
            plan_catalogue_removal(home, "team")


# Verify removal applies the registry changes and file deletion.
class RemoveCatalogueTests(CatalogueRemovalTestCase):
    # Remove a local catalogue while preserving unrelated state.
    def test_removes_a_local_catalogue_and_preserves_unrelated_state(self) -> None:
        # Prepare a registry with two catalogues, bindings, and unrelated content.
        home: Path = self.make_sandbox(
            "# Preserve this comment.\n"
            "[custom]\nvalue = 1\n\n"
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n\n'
            '[secrets.other.github]\nfile = "keys/github"\n'
        )

        # Prepare the catalogue directories and a host secret file.
        team_dir: Path = home / "catalogues" / "team"
        team_dir.mkdir(parents = True)
        other_dir: Path = home / "catalogues" / "other"
        other_dir.mkdir(parents = True)
        host_secret: Path = home / "keys" / "api_key"
        host_secret.parent.mkdir()
        host_secret.write_text("secret-value\n", encoding = "utf-8")

        # Plan and execute the removal.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")
        remove_catalogue(plan)

        # Require the installed catalogue files to be deleted.
        self.assertFalse(team_dir.exists())

        # Require the other catalogue, host secret, and unrelated content to survive.
        self.assertTrue(other_dir.exists())
        self.assertTrue(host_secret.exists())
        registry_file: Path = home / "catalogues.toml"
        text: str = registry_file.read_text(encoding = "utf-8")
        configuration: dict[str, Any] = tomllib.loads(text)
        self.assertNotIn("team", configuration["catalogues"])
        self.assertIn("other", configuration["catalogues"])
        self.assertNotIn("team", configuration["secrets"])
        self.assertIn("other", configuration["secrets"])
        self.assertIn("# Preserve this comment.", text)
        self.assertEqual(configuration["custom"], {"value": 1})

    # Remove a registration whose directory is already missing.
    def test_removes_a_registration_without_a_directory(self) -> None:
        # Prepare a local catalogue without creating its directory.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')

        # Plan and execute the removal.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")
        remove_catalogue(plan)

        # Require the registration to be removed.
        configuration: dict[str, Any] = tomllib.loads((home / "catalogues.toml").read_text(encoding = "utf-8"))
        self.assertNotIn("catalogues", configuration)

    # Leave the registry unchanged when deleting the directory fails.
    def test_deletion_failure_leaves_the_registry_unchanged(self) -> None:
        # Prepare a local catalogue and binding.
        home: Path = self.make_sandbox(
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n'
        )
        team_dir: Path = home / "catalogues" / "team"
        team_dir.mkdir(parents = True)
        registry_file: Path = home / "catalogues.toml"
        original: str = registry_file.read_text(encoding = "utf-8")

        # Plan the removal and fail the directory deletion.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")
        with mock.patch("sandbox.catalogue.removal.shutil.rmtree", side_effect = OSError("denied")):
            with self.assertRaises(IncompleteRemoval):
                remove_catalogue(plan)

        # Require the directory and registry to remain unchanged.
        self.assertTrue(team_dir.exists())
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)

    # Leave the registration for a rerun when the registry write fails after deletion.
    def test_write_failure_after_deletion_is_rerunnable(self) -> None:
        # Prepare a local catalogue and binding.
        home: Path = self.make_sandbox(
            '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n\n'
            '[secrets.team.api_key]\nfile = "keys/api_key"\n'
        )
        team_dir: Path = home / "catalogues" / "team"
        team_dir.mkdir(parents = True)
        registry_file: Path = home / "catalogues.toml"

        # Plan the removal and fail the registry write.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")
        with mock.patch("sandbox.configuration.registry.write_registry_atomic", side_effect = OSError("write failed")):
            with self.assertRaises(IncompleteRemoval):
                remove_catalogue(plan)

        # Require the files to be gone and the registration to remain for a rerun.
        self.assertFalse(team_dir.exists())
        configuration: dict[str, Any] = tomllib.loads(registry_file.read_text(encoding = "utf-8"))
        self.assertIn("team", configuration["catalogues"])
        self.assertIn("team", configuration["secrets"])

        # Rerun the removal and require the registration and bindings to disappear.
        remove_catalogue(plan)
        configuration = tomllib.loads(registry_file.read_text(encoding = "utf-8"))
        self.assertNotIn("catalogues", configuration)
        self.assertNotIn("secrets", configuration)

    # Refuse a plan whose registration changed since planning.
    def test_refuses_a_plan_with_a_changed_registration(self) -> None:
        # Prepare a local catalogue registration.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')
        team_dir: Path = home / "catalogues" / "team"
        team_dir.mkdir(parents = True)

        # Prepare a plan that records a different origin.
        plan: CatalogueRemovalPlan = CatalogueRemovalPlan(
            home = home,
            registration = CatalogueRegistration("team", "git", home / "catalogues" / "team"),
        )

        # Require the registration mismatch to be refused before any change.
        with self.assertRaises(RegistryError):
            remove_catalogue(plan)

        # Require the directory and registration to remain.
        self.assertTrue(team_dir.exists())
        self.assertIn("team", tomllib.loads((home / "catalogues.toml").read_text(encoding = "utf-8"))["catalogues"])

    # Refuse a plan bound to another sandbox directory.
    def test_refuses_a_plan_from_another_sandbox(self) -> None:
        # Prepare two sandboxes with the same catalogue registration.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')
        (home / "catalogues" / "team").mkdir(parents = True)
        other: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')
        (other / "catalogues" / "team").mkdir(parents = True)

        # Plan the removal in the first sandbox.
        plan: CatalogueRemovalPlan | None = plan_catalogue_removal(home, "team")
        self.assertIsNotNone(plan)
        if plan is None:
            self.fail("Expected the registered catalogue to produce a plan.")

        # Require the second sandbox to refuse the foreign plan.
        with self.assertRaisesRegex(RegistryError, "removal plan belongs to"):
            make_client(other).catalogues.remove(plan)

        # Require both catalogue directories to remain.
        self.assertTrue((home / "catalogues" / "team").is_dir())
        self.assertTrue((other / "catalogues" / "team").is_dir())

    # Reject a symbolic link at the canonical catalogue path before deletion.
    def test_rejects_a_symbolic_link_before_deletion(self) -> None:
        # Prepare a local catalogue registration and an external directory.
        home: Path = self.make_sandbox('[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n')
        (home / "catalogues").mkdir()
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        external_dir: Path = Path(temporary.name).resolve()
        (external_dir / "marker.txt").write_text("external", encoding = "utf-8")
        (home / "catalogues" / "team").symlink_to(external_dir, target_is_directory = True)
        registry_file: Path = home / "catalogues.toml"
        original: str = registry_file.read_text(encoding = "utf-8")

        # Require planning the removal to refuse the symbolic link.
        with self.assertRaises(RegistryError):
            plan_catalogue_removal(home, "team")

        # Require the external directory, symbolic link, and registry to remain.
        self.assertTrue((external_dir / "marker.txt").is_file())
        self.assertTrue((home / "catalogues" / "team").is_symlink())
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
