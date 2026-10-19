# Imports.
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import tomlkit

# Import fixtures.
from git_fixtures import GIT_AVAILABLE, GIT_ENVIRONMENT, make_git_repository

# Import helpers.
import sandbox.catalogue.install as catalogue_helper
import sandbox.catalogue.sources as source_helper

# Import models.
from sandbox.catalogue.manifest import load_catalogue
from sandbox.configuration.registry import load_registry
from sandbox.configuration.store import ConfigurationStore

# Import errors.
from sandbox.errors.catalogues import CatalogueInstallError, RegistryError
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind


# Verify bundled catalogue installation validates before publishing.
class InstallCatalogueTests(unittest.TestCase):
    # Verify the bundled catalogue is installed, loadable, and registered.
    def test_installs_and_validates_the_bundled_catalogue(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue.
        installed: Path = catalogue_helper.install_catalogue(home, "default", "bundled")

        # Require the manifest and no legacy volume file.
        self.assertEqual(installed, home.resolve() / "catalogues" / "default")
        self.assertTrue((installed / "catalogue.toml").is_file())
        self.assertFalse((installed / "volumes.toml").exists())

        # Require the installed manifest to load with the bundled name.
        self.assertEqual(load_catalogue(installed).name, "default")

        # Require the registry to resolve the installed catalogue.
        self.assertEqual(ConfigurationStore(home).resolve("default"), installed)

    # Verify the bundled catalogue installs under a custom name with a rewritten manifest.
    def test_installs_the_bundled_catalogue_under_a_custom_name(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Require the requested destination and a rewritten manifest name.
        self.assertEqual(installed, home.resolve() / "catalogues" / "alpha")
        self.assertEqual(load_catalogue(installed).name, "alpha")

        # Require the registry to register and resolve the custom name.
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["alpha"]
        self.assertEqual(dict(registration), {"type": "bundled", "path": "catalogues/alpha"})
        self.assertEqual(ConfigurationStore(home).resolve("alpha"), installed)

    # Verify reinstalling a custom name requires force.
    def test_reinstalls_a_custom_name_only_with_force(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Require an existing installation to reject replacement without force.
        with self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Require a forced reinstall to replace the existing catalogue.
        replaced: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled", force = True)
        self.assertEqual(replaced, installed)
        self.assertEqual(load_catalogue(replaced).name, "alpha")
        self.assertEqual(ConfigurationStore(home).resolve("alpha"), replaced)

    # Verify a forced reinstall replaces the previous catalogue files.
    def test_force_reinstall_removes_stale_files(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name with a stale file.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")
        stale_file: Path = installed / "stale.txt"
        stale_file.write_text("stale", encoding = "utf-8")

        # Require a refused reinstall to leave the stale file untouched.
        with self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(home, "alpha", "bundled")
        self.assertTrue(stale_file.exists())

        # Require a forced reinstall to remove the stale file.
        catalogue_helper.install_catalogue(home, "alpha", "bundled", force = True)
        self.assertFalse(stale_file.exists())
        self.assertEqual(load_catalogue(installed).name, "alpha")

    # Verify a forced reinstall preserves the existing registry mode.
    def test_force_reinstall_preserves_the_registry_mode(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue and restrict the registry permissions.
        catalogue_helper.install_catalogue(home, "team", "bundled")
        registry_file: Path = home.resolve() / "catalogues.toml"
        registry_file.chmod(0o600)

        # Require a forced reinstall to preserve the registry permissions.
        catalogue_helper.install_catalogue(home, "team", "bundled", force = True)
        self.assertEqual(registry_file.stat().st_mode & 0o777, 0o600)

    # Verify a failed forced reinstall preserves the previous catalogue and registry.
    def test_failed_forced_reinstall_preserves_the_previous_catalogue_and_registry(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Mark the previous catalogue to distinguish a rollback from a fresh copy.
        marker_file: Path = installed / "marker.txt"
        marker_file.write_text("original catalogue", encoding = "utf-8")

        # Save the published registry to detect any change.
        registry_file: Path = home.resolve() / "catalogues.toml"
        registry_before: str = registry_file.read_text(encoding = "utf-8")

        # Capture the real replacement function before patching it.
        real_replace: Callable[[Path, Path], None] = os.replace

        # Record every replacement destination to prove the destructive ordering.
        destinations: list[Path] = []

        # Fail only when publishing the registry.
        def fail_registry_publish(source: Path, destination: Path) -> None:
            # Record the replacement destination.
            destinations.append(Path(destination))

            # If the destination is the registry file.
            if Path(destination) == registry_file:
                # Throw.
                raise OSError("Simulated registry publish failure.")

            # Delegate every other replacement to the real implementation.
            real_replace(source, destination)

        # Require the forced reinstall to fail while publishing the registry.
        with mock.patch("sandbox.catalogue.install.os.replace", side_effect = fail_registry_publish):
            with self.assertRaises(CatalogueInstallError):
                catalogue_helper.install_catalogue(home, "alpha", "bundled", force = True)

        # Require the catalogue directory to be replaced before the registry is published.
        self.assertLess(destinations.index(installed), destinations.index(registry_file))

        # Require the previous catalogue to remain loadable and registered.
        self.assertEqual(load_catalogue(installed).name, "alpha")
        self.assertEqual(ConfigurationStore(home).resolve("alpha"), installed)

        # Require the marker of the previous catalogue to survive the rollback.
        self.assertEqual(marker_file.read_text(encoding = "utf-8"), "original catalogue")

        # Require the registry to remain byte-identical.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), registry_before)

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".alpha-*")), [])

    # Verify a forced reinstall restores the previous catalogue when installing the staged copy fails.
    def test_forced_reinstall_failure_while_installing_the_staged_catalogue_restores_the_previous_catalogue(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Mark the previous catalogue to distinguish a rollback from a fresh copy.
        marker_file: Path = installed / "marker.txt"
        marker_file.write_text("original catalogue", encoding = "utf-8")

        # Save the published registry to detect any change.
        registry_file: Path = home.resolve() / "catalogues.toml"
        registry_before: str = registry_file.read_text(encoding = "utf-8")

        # Capture the real replacement function before patching it.
        real_replace: Callable[[Path, Path], None] = os.replace

        # Fail only when installing the staged catalogue into the catalogue directory.
        def fail_staged_install(source: Path, destination: Path) -> None:
            # If the destination is the catalogue directory and the source is the staged catalogue.
            if Path(destination) == installed and Path(source).name == "catalogue":
                # Throw.
                raise OSError("Simulated staged catalogue install failure.")

            # Delegate every other replacement, including the backup and rollback, to the real implementation.
            real_replace(source, destination)

        # Require the forced reinstall to fail between the backup and the staged installation.
        with mock.patch("sandbox.catalogue.install.os.replace", side_effect = fail_staged_install):
            with self.assertRaises(CatalogueInstallError):
                catalogue_helper.install_catalogue(home, "alpha", "bundled", force = True)

        # Require the marker of the previous catalogue to be restored with its original content.
        self.assertEqual(marker_file.read_text(encoding = "utf-8"), "original catalogue")

        # Require the previous catalogue to remain loadable and registered.
        self.assertEqual(load_catalogue(installed).name, "alpha")
        self.assertEqual(ConfigurationStore(home).resolve("alpha"), installed)

        # Require the registry to remain byte-identical.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), registry_before)

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".alpha-*")), [])

    # Verify a failed fresh install leaves no catalogue directory and no registry file.
    def test_failed_fresh_install_publishes_no_catalogue_and_no_registry(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Capture the real replacement function before patching it.
        real_replace: Callable[[Path, Path], None] = os.replace

        # Fail only when publishing the registry.
        def fail_registry_publish(source: Path, destination: Path) -> None:
            # If the destination is the registry file.
            if Path(destination) == home.resolve() / "catalogues.toml":
                # Throw.
                raise OSError("Simulated registry publish failure.")

            # Delegate every other replacement to the real implementation.
            real_replace(source, destination)

        # Require the fresh install to fail while publishing the registry.
        with mock.patch("sandbox.catalogue.install.os.replace", side_effect = fail_registry_publish):
            with self.assertRaises(CatalogueInstallError):
                catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Require no catalogue directory and no registry file to remain.
        self.assertFalse((home / "catalogues" / "alpha").exists())
        self.assertFalse((home / "catalogues.toml").exists())

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".alpha-*")), [])

    # Verify a custom installation preserves the manifest comments and sections.
    def test_custom_name_install_preserves_manifest_comments_and_sections(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under a custom name.
        installed: Path = catalogue_helper.install_catalogue(home, "alpha", "bundled")
        manifest_text: str = (installed / "catalogue.toml").read_text(encoding = "utf-8")

        # Require the name to be rewritten and the original comments to survive.
        self.assertEqual(load_catalogue(installed).name, "alpha")
        self.assertIn('name = "alpha"', manifest_text)
        self.assertIn("# Catalogue metadata.", manifest_text)

        # Require unrelated manifest sections to survive the rewrite.
        self.assertIn("[volumes.omp]", manifest_text)
        self.assertIn("[recipes.r]", manifest_text)

        # Require no default catalogue to be created.
        self.assertFalse((home / "catalogues" / "default").exists())

    # Verify a default installation copies the bundled manifest unchanged.
    def test_default_install_keeps_the_bundled_manifest_byte_identical(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Install the bundled catalogue under its default name.
        installed: Path = catalogue_helper.install_catalogue(home, "default", "bundled")

        # Require the installed manifest to match the bundled source bytes.
        source_manifest: Path = Path(__file__).resolve().parents[1] / "catalogues" / "default" / "catalogue.toml"
        self.assertEqual((installed / "catalogue.toml").read_bytes(), source_manifest.read_bytes())

    # Verify a custom installation preserves other registry entries.
    def test_custom_installation_preserves_other_registry_entries(self) -> None:
        # Create an isolated sandbox directory with another registration.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"
        home.mkdir(parents = True)
        (home / "catalogues.toml").write_text(
            '# Registered development `sandbox` catalogues.\n\n[catalogues.other]\ntype = "local"\npath = "catalogues/other"\n',
            encoding = "utf-8",
        )

        # Install the bundled catalogue under a custom name.
        catalogue_helper.install_catalogue(home, "alpha", "bundled")

        # Require the unrelated registration to survive.
        registry_document: tomlkit.TOMLDocument = load_registry(home / "catalogues.toml")
        self.assertEqual(dict(registry_document["catalogues"]["other"]), {"type": "local", "path": "catalogues/other"})
        self.assertEqual(dict(registry_document["catalogues"]["alpha"]), {"type": "bundled", "path": "catalogues/alpha"})

    # Verify an invalid catalogue name is rejected before installation.
    def test_rejects_an_invalid_catalogue_name(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Require an invalid name to be rejected.
        with self.assertRaises(ConfigurationError):
            catalogue_helper.install_catalogue(home, "Invalid Name", "bundled")

        # Require no catalogue directory or registry.
        self.assertFalse((home / "catalogues").exists())
        self.assertFalse((home / "catalogues.toml").exists())

    # Verify a malformed bundled manifest is reported as an installation error.
    def test_reports_a_malformed_bundled_manifest_when_rewriting_the_name(self) -> None:
        # Create a temporary source tree with a malformed bundled manifest.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source_root: Path = Path(temporary.name) / "source"
        source_catalogue: Path = source_root / "catalogues" / "default"
        source_catalogue.mkdir(parents = True)

        # Require malformed TOML to be reported as an installation error.
        (source_catalogue / "catalogue.toml").write_text("[catalogue\n", encoding = "utf-8")
        with mock.patch("sandbox.catalogue.sources.resources.files", return_value = source_root), self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(Path(temporary.name) / "invalid", "alpha", "bundled")

        # Require a missing catalogue table to be reported as an installation error.
        (source_catalogue / "catalogue.toml").write_text('[recipes.base]\ncompose = "compose.yaml"\n', encoding = "utf-8")
        with mock.patch("sandbox.catalogue.sources.resources.files", return_value = source_root), self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(Path(temporary.name) / "missing", "alpha", "bundled")

        # Require no published catalogue or registry.
        self.assertFalse((Path(temporary.name) / "invalid" / "catalogues" / "alpha").exists())
        self.assertFalse((Path(temporary.name) / "invalid" / "catalogues.toml").exists())

    # Verify a bundled source that overlaps the final destination is never replaced.
    def test_rejects_a_bundled_source_that_overlaps_the_destination(self) -> None:
        # Create a repository-like source tree whose bundled catalogue is the destination.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source_root: Path = Path(temporary.name) / "repo"
        source_catalogue: Path = source_root / "catalogues" / "default"
        shutil.copytree(Path(__file__).resolve().parents[1] / "catalogues" / "default", source_catalogue)
        manifest_before: bytes = (source_catalogue / "catalogue.toml").read_bytes()

        # Require the overlapping bundled source to be rejected despite force.
        with mock.patch("sandbox.catalogue.sources.resources.files", return_value = source_root):
            with self.assertRaises(CatalogueInstallError) as raised:
                catalogue_helper.install_catalogue(source_root, "default", "bundled", force = True)
        self.assertIn("overlaps the catalogue destination", str(raised.exception))

        # Require the repository source and its absence of registration to survive.
        self.assertEqual((source_catalogue / "catalogue.toml").read_bytes(), manifest_before)
        self.assertFalse((source_root / "catalogues.toml").exists())

    # Verify an invalid staged catalogue is never published.
    def test_invalid_staged_catalogue_is_not_published(self) -> None:
        # Create an isolated sandbox directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Require validation failures to abort publication.
        with mock.patch.object(catalogue_helper.manifest, "load_catalogue", side_effect = ConfigurationError("", "Invalid catalogue.")):
            with self.assertRaises(ConfigurationError):
                catalogue_helper.install_catalogue(home, "default", "bundled")

        # Require no published catalogue or registry.
        self.assertFalse((home / "catalogues" / "default").exists())
        self.assertFalse((home / "catalogues.toml").exists())


# Verify local catalogue installation copies, rewrites, and registers its source.
class LocalCatalogueInstallTests(unittest.TestCase):
    # Copy the bundled catalogue into a temporary local directory.
    def make_source(self, root: Path) -> Path:
        # Copy the bundled catalogue to use as a valid local source.
        source: Path = root / "source"
        shutil.copytree(Path(__file__).resolve().parents[1] / "catalogues" / "default", source)

        # Return the local source directory.
        return source

    # Install a local catalogue, rewrite its manifest, and register its origin.
    def test_installs_a_local_catalogue_and_rewrites_the_manifest(self) -> None:
        # Prepare an isolated sandbox and local source.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = self.make_source(root)

        # Install the local catalogue under a different name.
        installed: Path = catalogue_helper.install_catalogue(home, "team", str(source))

        # Require the installed copy and rewritten manifest name.
        self.assertEqual(installed, home.resolve() / "catalogues" / "team")
        self.assertEqual(load_catalogue(installed).name, "team")

        # Require the source to remain unchanged.
        self.assertEqual(load_catalogue(source).name, "default")

        # Require the local origin, normalized path, and successful resolution.
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "local", "path": "catalogues/team"})
        self.assertEqual(ConfigurationStore(home).resolve("team"), installed)

    # Preserve symlinks when copying a local catalogue.
    def test_local_install_preserves_symlinks(self) -> None:
        # Prepare a local source with a symbolic link.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = self.make_source(root)
        (source / "linked.toml").symlink_to("catalogue.toml")

        # Install the local catalogue.
        installed: Path = catalogue_helper.install_catalogue(home, "team", str(source))

        # Require the symbolic link to be copied as a link.
        self.assertTrue((installed / "linked.toml").is_symlink())
        self.assertEqual(os.readlink(installed / "linked.toml"), "catalogue.toml")

    # Preserve the manifest bytes when the source name already matches.
    def test_local_install_preserves_matching_manifest_bytes(self) -> None:
        # Prepare an isolated sandbox and local source.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = self.make_source(root)

        # Install the local catalogue under its existing name.
        installed: Path = catalogue_helper.install_catalogue(home, "default", str(source))

        # Require the manifest to remain byte-identical.
        self.assertEqual((installed / "catalogue.toml").read_bytes(), (source / "catalogue.toml").read_bytes())

        # Require the local origin to be recorded.
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["default"]
        self.assertEqual(dict(registration), {"type": "local", "path": "catalogues/default"})

    # Reject empty, missing, and non-directory local sources before touching the sandbox.
    def test_rejects_invalid_local_sources(self) -> None:
        # Prepare an isolated sandbox and a regular file.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        regular_file: Path = root / "catalogue.toml"
        regular_file.write_text("", encoding = "utf-8")

        # Cover an empty source, a missing directory, and a regular file.
        sources: tuple[str, ...] = ("", str(root / "missing"), str(regular_file))
        for source in sources:
            with self.subTest(source = source):
                # Require the invalid source to be rejected.
                with self.assertRaises(CatalogueInstallError):
                    catalogue_helper.install_catalogue(home, "team", source)

        # Require no sandbox content.
        self.assertFalse(home.exists())

    # Reject malformed and empty local manifests without publishing.
    def test_rejects_malformed_and_empty_local_manifests(self) -> None:
        # Cover malformed TOML and an empty manifest.
        manifests: tuple[str, ...] = ("[catalogue\n", "")
        for manifest in manifests:
            with self.subTest(manifest = manifest):
                # Prepare an isolated sandbox and a local source.
                temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
                self.addCleanup(temporary.cleanup)
                root: Path = Path(temporary.name)
                home: Path = root / "sandbox"
                source: Path = root / "source"
                source.mkdir()
                (source / "catalogue.toml").write_text(manifest, encoding = "utf-8")

                # Require the invalid manifest to be rejected.
                with self.assertRaises(CatalogueInstallError):
                    catalogue_helper.install_catalogue(home, "team", str(source))

                # Require no published catalogue or registry.
                self.assertFalse((home / "catalogues" / "team").exists())
                self.assertFalse((home / "catalogues.toml").exists())

    # Reject a local source equal to the final destination.
    def test_rejects_a_source_equal_to_the_final_destination(self) -> None:
        # Prepare a final destination that is also the source.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = home / "catalogues" / "team"
        shutil.copytree(Path(__file__).resolve().parents[1] / "catalogues" / "default", source)

        # Require the self-copy to be rejected despite force.
        with self.assertRaises(CatalogueInstallError) as raised:
            catalogue_helper.install_catalogue(home, "team", str(source), force = True)
        self.assertIn("overlaps the catalogue destination", str(raised.exception))
        self.assertIn(str(source.resolve()), str(raised.exception))

        # Require the source and its absence of registration to survive.
        self.assertTrue((source / "catalogue.toml").is_file())
        self.assertFalse((home / "catalogues.toml").exists())

    # Reject a local source nested inside the final destination.
    def test_rejects_a_source_inside_the_final_destination(self) -> None:
        # Prepare a source nested inside the final destination.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = home / "catalogues" / "team" / "inner"
        shutil.copytree(Path(__file__).resolve().parents[1] / "catalogues" / "default", source)

        # Require the nested source to be rejected despite force.
        with self.assertRaises(CatalogueInstallError) as raised:
            catalogue_helper.install_catalogue(home, "team", str(source), force = True)
        self.assertIn("overlaps the catalogue destination", str(raised.exception))

        # Require the source and its absence of registration to survive.
        self.assertTrue((source / "catalogue.toml").is_file())
        self.assertFalse((home / "catalogues.toml").exists())

    # Reject a local source that contains the final destination.
    def test_rejects_a_source_that_contains_the_final_destination(self) -> None:
        # Prepare a source that contains the final destination.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"
        source: Path = home / "catalogues"
        source.mkdir(parents = True)
        marker_file: Path = source / "marker.txt"
        marker_file.write_text("source", encoding = "utf-8")

        # Require the containing source to be rejected despite force.
        with self.assertRaises(CatalogueInstallError) as raised:
            catalogue_helper.install_catalogue(home, "team", str(source), force = True)
        self.assertIn("overlaps the catalogue destination", str(raised.exception))

        # Require the source and its absence of registration to survive.
        self.assertTrue(marker_file.is_file())
        self.assertFalse((home / "catalogues.toml").exists())
        self.assertFalse((source / "team").exists())

    # Replace a bundled catalogue with a local source when forced.
    def test_force_replaces_a_bundled_catalogue_with_a_local_origin(self) -> None:
        # Prepare an isolated sandbox and local source.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = self.make_source(root)
        (source / "marker.txt").write_text("local catalogue", encoding = "utf-8")

        # Install the bundled catalogue under a custom name with a stale file.
        installed: Path = catalogue_helper.install_catalogue(home, "team", "bundled")
        stale_file: Path = installed / "stale.txt"
        stale_file.write_text("stale", encoding = "utf-8")

        # Replace the bundled catalogue from the local source.
        replaced: Path = catalogue_helper.install_catalogue(home, "team", str(source), force = True)

        # Require the local content and origin to replace the bundled installation.
        self.assertEqual(replaced, installed)
        self.assertFalse(stale_file.exists())
        self.assertTrue((replaced / "marker.txt").is_file())
        self.assertEqual(load_catalogue(replaced).name, "team")
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "local", "path": "catalogues/team"})

    # Replace a local catalogue with the bundled source when forced.
    def test_force_replaces_a_local_catalogue_with_the_bundled_origin(self) -> None:
        # Prepare an isolated sandbox and local source with a marker.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        source: Path = self.make_source(root)
        (source / "marker.txt").write_text("local catalogue", encoding = "utf-8")

        # Install the local catalogue.
        installed: Path = catalogue_helper.install_catalogue(home, "team", str(source))
        self.assertTrue((installed / "marker.txt").is_file())

        # Replace the local catalogue with the bundled source.
        replaced: Path = catalogue_helper.install_catalogue(home, "team", "bundled", force = True)

        # Require the bundled content and origin to replace the local installation.
        self.assertEqual(replaced, installed)
        self.assertFalse((replaced / "marker.txt").exists())
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "bundled", "path": "catalogues/team"})

    # Refuse an existing registration without force even when its directory is missing.
    def test_refuses_an_existing_registration_without_force(self) -> None:
        # Prepare a sandbox with a canonical registration but no directory.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"
        home.mkdir()
        registry_file: Path = home / "catalogues.toml"
        original: str = '[catalogues.team]\ntype = "local"\npath = "catalogues/team"\n'
        registry_file.write_text(original, encoding = "utf-8")

        # Require the existing registration to be refused.
        with self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(home, "team", "bundled")

        # Require the registry to remain unchanged.
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)

    # Refuse a noncanonical registration even when forced.
    def test_force_refuses_a_noncanonical_registration(self) -> None:
        # Prepare a sandbox with a noncanonical registration.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"
        home.mkdir()
        registry_file: Path = home / "catalogues.toml"
        original: str = '[catalogues.team]\ntype = "local"\npath = "elsewhere/team"\n'
        registry_file.write_text(original, encoding = "utf-8")

        # Require the noncanonical registration to be refused despite force.
        with self.assertRaises(RegistryError):
            catalogue_helper.install_catalogue(home, "team", "bundled", force = True)

        # Require no catalogue and no registry change.
        self.assertFalse((home / "catalogues" / "team").exists())
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), original)


# Verify unsupported `git` source schemes are rejected clearly.
class GitSourceValidationTests(unittest.TestCase):
    # Reject `git+` and unknown schemes.
    def test_rejects_unsupported_git_schemes(self) -> None:
        # Cover the `git+` prefix and an unknown scheme.
        sources: tuple[str, ...] = (
            "git+https://example.com/team/catalogue.git",
            "foo://example.com/team/catalogue.git",
        )
        for source in sources:
            with self.subTest(source = source):
                # Require an actionable unsupported-source error.
                with self.assertRaises(CatalogueInstallError) as raised:
                    source_helper.source_for(source)
                self.assertIn("supported", str(raised.exception))


# Verify source values are classified by origin.
@unittest.skipUnless(GIT_AVAILABLE, "`git` is not available.")
class CatalogueSourceClassificationTests(unittest.TestCase):
    # Classify bundled, local, and `git`-like values.
    def test_classifies_supported_source_values(self) -> None:
        # Require the bundled source.
        self.assertIsInstance(source_helper.source_for("bundled"), source_helper.BundledSource)

        # Require a local directory source.
        repository_root: Path = Path(__file__).resolve().parents[1]
        self.assertIsInstance(source_helper.source_for(str(repository_root)), source_helper.LocalSource)

        # Cover every supported `git` URL form.
        git_sources: tuple[str, ...] = (
            "https://example.com/team/catalogue.git",
            "http://example.com/team/catalogue.git",
            "ssh://git@example.com/team/catalogue.git",
            "git://example.com/team/catalogue.git",
            "file:///tmp/catalogue",
            "git@example.com:team/catalogue.git",
        )
        for source in git_sources:
            with self.subTest(source = source):
                # Require the `git` source and origin.
                classified: source_helper.CatalogueSource = source_helper.source_for(source)
                self.assertIsInstance(classified, source_helper.GitSource)
                self.assertEqual(classified.origin, "git")


# Verify a missing `git` executable is reported clearly.
class GitAvailabilityTests(unittest.TestCase):
    # Report a missing `git` executable clearly before publishing.
    def test_missing_git_is_reported_clearly(self) -> None:
        # Create an isolated sandbox.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Require the typed prerequisite when `git` is unavailable.
        with mock.patch("sandbox.catalogue.sources.shutil.which", return_value = None):
            with self.assertRaises(PrerequisiteError) as raised:
                catalogue_helper.install_catalogue(home, "team", "https://example.com/team/catalogue.git")
        self.assertEqual(raised.exception.tool, "git")
        self.assertIs(raised.exception.kind, PrerequisiteKind.MISSING)
        self.assertEqual(raised.exception.operation, "catalogue.install")
        self.assertIn("Install git", raised.exception.hint or "")

        # Require no sandbox content.
        self.assertFalse(home.exists())

    # Report an unlaunchable `git` executable as an unusable prerequisite.
    def test_unlaunchable_git_is_a_prerequisite(self) -> None:
        # Create an isolated sandbox.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home: Path = Path(temporary.name) / "sandbox"

        # Require the typed prerequisite when `git` cannot be launched.
        with (
            mock.patch("sandbox.catalogue.sources.shutil.which", return_value = "/usr/bin/git"),
            mock.patch("sandbox.catalogue.sources.subprocess.Popen", side_effect = PermissionError("denied")),
        ):
            with self.assertRaises(PrerequisiteError) as raised:
                catalogue_helper.install_catalogue(home, "team", "https://example.com/team/catalogue.git")
        self.assertEqual(raised.exception.tool, "git")
        self.assertIs(raised.exception.kind, PrerequisiteKind.UNUSABLE)
        self.assertEqual(raised.exception.operation, "catalogue.install")
        self.assertIn("denied", raised.exception.diagnostic)
        self.assertIsNotNone(raised.exception.hint)

        # Require no published catalogue or registry.
        self.assertFalse((home / "catalogues" / "team").exists())
        self.assertFalse((home / "catalogues.toml").exists())


# Verify `git` catalogue installation clones, registers, and preserves its source.
@unittest.skipUnless(GIT_AVAILABLE, "`git` is not available.")
class GitCatalogueInstallTests(unittest.TestCase):
    # Isolate `git` configuration for offline tests.
    def setUp(self) -> None:
        # Apply the isolated `git` environment.
        super().setUp()
        patcher: Any = mock.patch.dict(os.environ, GIT_ENVIRONMENT)
        patcher.start()
        self.addCleanup(patcher.stop)

    # Install a `git` catalogue and retain the cloned repository.
    def test_installs_a_git_catalogue_and_retains_the_repository(self) -> None:
        # Create an isolated sandbox and offline repository.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        repository: Path = make_git_repository(root)

        # Install the `git` catalogue under a different name.
        installed: Path = catalogue_helper.install_catalogue(home, "team", repository.as_uri())

        # Require the installed copy, retained repository, and rewritten manifest.
        self.assertEqual(installed, home.resolve() / "catalogues" / "team")
        self.assertTrue((installed / ".git" / "HEAD").is_file())
        self.assertEqual(load_catalogue(installed).name, "team")

        # Require the source repository to remain unchanged.
        self.assertEqual(load_catalogue(repository).name, "default")
        self.assertTrue((repository / ".git").is_dir())

        # Require the `git` origin, normalized path, and successful resolution.
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "git", "path": "catalogues/team"})
        self.assertEqual(ConfigurationStore(home).resolve("team"), installed)

    # Preserve the manifest bytes when the `git` catalogue name already matches.
    def test_git_install_preserves_matching_manifest_bytes(self) -> None:
        # Create an isolated sandbox and offline repository.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        repository: Path = make_git_repository(root)

        # Install the `git` catalogue under its existing name.
        installed: Path = catalogue_helper.install_catalogue(home, "default", repository.as_uri())

        # Require the manifest to remain byte-identical.
        self.assertEqual((installed / "catalogue.toml").read_bytes(), (repository / "catalogue.toml").read_bytes())

        # Require the `git` origin to be recorded.
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["default"]
        self.assertEqual(dict(registration), {"type": "git", "path": "catalogues/default"})

    # Report a clone failure without publishing a catalogue.
    def test_clone_failure_without_a_previous_installation(self) -> None:
        # Create an isolated sandbox and a missing local repository URL.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        missing_url: str = (root / "missing").as_uri()

        # Require the clone failure to report only its exit code.
        with self.assertRaises(CatalogueInstallError) as raised:
            catalogue_helper.install_catalogue(home, "team", missing_url)
        message: str = str(raised.exception)
        self.assertIn("exit code", message)
        self.assertNotIn(missing_url, message)
        self.assertNotIn(str(root), message)

        # Require no published catalogue or registry.
        self.assertFalse((home / "catalogues" / "team").exists())
        self.assertFalse((home / "catalogues.toml").exists())

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".team-*")), [])

    # Preserve the previous installation when a forced replacement clone fails.
    def test_clone_failure_during_forced_replacement_preserves_the_previous_state(self) -> None:
        # Create an isolated sandbox and install the bundled catalogue.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        installed: Path = catalogue_helper.install_catalogue(home, "team", "bundled")
        marker_file: Path = installed / "marker.txt"
        marker_file.write_text("original catalogue", encoding = "utf-8")
        registry_file: Path = home.resolve() / "catalogues.toml"
        registry_before: str = registry_file.read_text(encoding = "utf-8")

        # Require the forced replacement to fail while cloning.
        with self.assertRaises(CatalogueInstallError):
            catalogue_helper.install_catalogue(home, "team", (root / "missing").as_uri(), force = True)

        # Require the previous catalogue, marker, and registry to survive.
        self.assertEqual(marker_file.read_text(encoding = "utf-8"), "original catalogue")
        self.assertEqual(load_catalogue(installed).name, "team")
        self.assertEqual(registry_file.read_text(encoding = "utf-8"), registry_before)

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".team-*")), [])

    # Report a clone timeout without leaking the URL.
    def test_clone_timeout_is_reported(self) -> None:
        # Create an isolated sandbox and offline repository.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        repository: Path = make_git_repository(root)

        # Simulate a clone that exceeds the fixed timeout.
        process: mock.Mock = mock.Mock()
        process.pid = 4321
        process.returncode = -signal.SIGKILL
        process.communicate.side_effect = [subprocess.TimeoutExpired(["git", "clone"], 120), None]
        with (
            mock.patch("sandbox.catalogue.sources.subprocess.Popen", return_value = process),
            mock.patch("sandbox.catalogue.sources.os.getpgid", return_value = 5678),
            mock.patch("sandbox.catalogue.sources.os.killpg") as killpg,
        ):
            with self.assertRaises(CatalogueInstallError) as raised:
                catalogue_helper.install_catalogue(home, "team", repository.as_uri())

        # Require the process group to be killed and the process to be reaped.
        killpg.assert_called_once_with(5678, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

        # Require the timeout to be reported without the URL.
        message: str = str(raised.exception)
        self.assertIn("timed out after 120 seconds", message)
        self.assertNotIn(repository.as_uri(), message)

        # Require no published catalogue or registry.
        self.assertFalse((home / "catalogues" / "team").exists())
        self.assertFalse((home / "catalogues.toml").exists())

        # Require no staging directory to remain.
        self.assertEqual(list((home / "catalogues").glob(".team-*")), [])

    # Clean up the clone process tree when the user interrupts.
    def test_keyboard_interrupt_kills_the_clone_process_tree(self) -> None:
        # Prepare a `git` source and a fake clone.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        source: source_helper.GitSource = source_helper.GitSource("https://example.com/team/catalogue.git")
        process: mock.Mock = mock.Mock()
        process.pid = 4321
        process.communicate.side_effect = [KeyboardInterrupt(), None]

        # Interrupt the clone while it is waiting.
        with (
            mock.patch("sandbox.catalogue.sources.subprocess.Popen", return_value = process),
            mock.patch("sandbox.catalogue.sources.os.getpgid", return_value = 5678),
            mock.patch("sandbox.catalogue.sources.os.killpg") as killpg,
        ):
            with self.assertRaises(KeyboardInterrupt):
                source.materialize(root / "staging", root / "destination")

        # Require the process group to be killed, the process reaped, and the interruption re-raised.
        killpg.assert_called_once_with(5678, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

    # Run `git` non-interactively and redact clone output.
    def test_clone_is_non_interactive_and_redacts_output(self) -> None:
        # Prepare a `git` source and a fake successful clone.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        url: str = "https://user:secret@example.com/team/catalogue.git"
        source: source_helper.GitSource = source_helper.GitSource(url)
        process: mock.Mock = mock.Mock()
        process.pid = 12345
        process.returncode = 0
        process.communicate.return_value = None

        # Record the clone invocation while inherited askpass helpers are set.
        with (
            mock.patch.dict(os.environ, {"GIT_ASKPASS": "/tmp/askpass", "SSH_ASKPASS": "/tmp/ssh"}),
            mock.patch("sandbox.catalogue.sources.subprocess.Popen", return_value = process) as popen,
        ):
            source.materialize(root / "staging", root / "destination")

        # Require the shallow clone command and non-interactive environment.
        command: list[str] = popen.call_args.args[0]
        self.assertEqual(command, ["git", "clone", "--depth", "1", "--", url, str(root / "staging")])
        environment: dict[str, str] = popen.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(environment["GCM_INTERACTIVE"], "never")
        self.assertEqual(environment["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")
        self.assertEqual(environment["GIT_ASKPASS"], "false")
        self.assertEqual(environment["SSH_ASKPASS"], "false")
        self.assertIs(popen.call_args.kwargs["start_new_session"], True)
        self.assertIs(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(popen.call_args.kwargs["stderr"], subprocess.DEVNULL)

        # Require clone failures to expose only the exit code.
        failure: mock.Mock = mock.Mock()
        failure.pid = 12345
        failure.returncode = 128
        failure.communicate.return_value = None
        with mock.patch("sandbox.catalogue.sources.subprocess.Popen", return_value = failure):
            with self.assertRaises(CatalogueInstallError) as raised:
                source.materialize(root / "staging", root / "destination")
        message: str = str(raised.exception)
        self.assertIn("exit code 128", message)
        self.assertNotIn(url, message)
        self.assertNotIn("secret", message)
        self.assertNotIn("example.com", message)

    # Kill the whole clone process tree when the timeout expires.
    def test_timeout_kills_the_clone_process_tree(self) -> None:
        # Create a fake `git` executable that spawns a child and hangs.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        fake_bin: Path = root / "bin"
        fake_bin.mkdir()
        parent_file: Path = root / "parent.pid"
        child_file: Path = root / "child.pid"
        fake_git: Path = fake_bin / "git"
        fake_git.write_text(
            f"""#!{sys.executable}
import os
import subprocess
import sys
import time

with open({str(parent_file)!r}, "w", encoding = "utf-8") as stream:
    stream.write(str(os.getpid()))

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open({str(child_file)!r}, "w", encoding = "utf-8") as stream:
    stream.write(str(child.pid))

time.sleep(60)
""",
            encoding = "utf-8",
        )
        fake_git.chmod(0o755)
        home: Path = root / "sandbox"

        # Require the short timeout to kill the clone and its child.
        try:
            with (
                mock.patch.dict(os.environ, {"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"}),
                mock.patch.object(source_helper, "GIT_CLONE_TIMEOUT", 2.0),
            ):
                with self.assertRaises(CatalogueInstallError) as raised:
                    catalogue_helper.install_catalogue(home, "team", "https://example.com/team/catalogue.git")
            self.assertIn("timed out", str(raised.exception))

            # Require both the clone and its child to be gone.
            parent_pid: int = int(parent_file.read_text(encoding = "utf-8"))
            child_pid: int = int(child_file.read_text(encoding = "utf-8"))
            self.assertTrue(self.wait_for_process_exit(parent_pid))
            self.assertTrue(self.wait_for_process_exit(child_pid))

            # Require no staging directory to remain.
            self.assertEqual(list((home / "catalogues").glob(".team-*")), [])

        # Kill any process that survived a failed assertion.
        finally:
            for pid_file in (parent_file, child_file):
                if not pid_file.is_file():
                    continue
                try:
                    os.kill(int(pid_file.read_text(encoding = "utf-8")), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass

    # Wait for a process to disappear.
    def wait_for_process_exit(self, pid: int, timeout: float = 5.0) -> bool:
        # Poll until the process is gone or the deadline passes.
        deadline: float = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.05)
        return False

    # Replace a bundled catalogue with a `git` source when forced.
    def test_force_replaces_a_bundled_catalogue_with_git(self) -> None:
        # Create an isolated sandbox and offline repository.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        repository: Path = make_git_repository(root)

        # Install the bundled catalogue with a stale file.
        installed: Path = catalogue_helper.install_catalogue(home, "team", "bundled")
        stale_file: Path = installed / "stale.txt"
        stale_file.write_text("stale", encoding = "utf-8")

        # Replace the bundled catalogue with the `git` source.
        replaced: Path = catalogue_helper.install_catalogue(home, "team", repository.as_uri(), force = True)

        # Require the `git` content and origin to replace the bundled installation.
        self.assertEqual(replaced, installed)
        self.assertFalse(stale_file.exists())
        self.assertTrue((replaced / ".git").is_dir())
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "git", "path": "catalogues/team"})

    # Replace a `git` catalogue with the bundled source when forced.
    def test_force_replaces_a_git_catalogue_with_bundled(self) -> None:
        # Create an isolated sandbox and offline repository.
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root: Path = Path(temporary.name)
        home: Path = root / "sandbox"
        repository: Path = make_git_repository(root)

        # Install the `git` catalogue.
        installed: Path = catalogue_helper.install_catalogue(home, "team", repository.as_uri())
        self.assertTrue((installed / ".git").is_dir())

        # Replace the `git` catalogue with the bundled source.
        replaced: Path = catalogue_helper.install_catalogue(home, "team", "bundled", force = True)

        # Require the bundled content and origin to replace the `git` installation.
        self.assertEqual(replaced, installed)
        self.assertFalse((replaced / ".git").exists())
        registration: Any = load_registry(home / "catalogues.toml")["catalogues"]["team"]
        self.assertEqual(dict(registration), {"type": "bundled", "path": "catalogues/team"})

# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
