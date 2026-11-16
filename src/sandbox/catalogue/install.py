# Imports.
import os
import shutil
import tempfile
from collections.abc import MutableMapping
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

# Import catalogue declarations.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.catalogue.loader import CatalogueLoader
from sandbox.catalogue.manifest import manifest_path
from sandbox.catalogue.sources.layout import SourceLayout
from sandbox.catalogue.sources.source import CatalogueSource

# Import configuration.
from sandbox.configuration.store import ConfigurationStore

# Import errors.
from sandbox.errors.catalogues import CatalogueInstallError


# Install catalogues below the managed catalogue root.
class CatalogueInstaller:
    # Configuration store.
    store: ConfigurationStore

    # Install and publish one catalogue under the requested name.
    def _install(self: "CatalogueInstaller", name: str, source: CatalogueSource, *, which: str | None = None, force: bool = False) -> Path:
        # Compute the destination, validating the name.
        catalogue_dir: Path = self.store.destination(name)

        # Determine whether the directory already exists.
        directory_exists: bool = catalogue_dir.exists() or catalogue_dir.is_symlink()

        # Determine whether the catalogue is already registered.
        registered: bool = self.store.registration(name) is not None

        # If replacing an existing installation without permission.
        if (directory_exists or registered) and not force:
            # Throw.
            raise CatalogueInstallError(f"Catalogue `{name}` is already installed. Use `--force` to replace it.")

        # If the destination is a symbolic link or not a directory.
        if catalogue_dir.is_symlink() or (catalogue_dir.exists() and not catalogue_dir.is_dir()):
            # Throw.
            raise CatalogueInstallError(f"Catalogue destination `{catalogue_dir}` is not a regular directory.")

        # Validate the registration before changing the filesystem.
        self.store.check_registration(name, source.origin, force)

        # Create the catalogue root before staging.
        catalogue_dir.parent.mkdir(parents = True, exist_ok = True)

        # Create the staging directory.
        staging_dir: Path = Path(tempfile.mkdtemp(prefix = f".{name}-", dir = catalogue_dir.parent))

        # Prepare the staged source and backup paths.
        staged_source: Path = staging_dir / "catalogue"
        backup_catalogue: Path = staging_dir / "backup"

        # Track whether the previous installation was backed up.
        backed_up: bool = False

        # Track whether the new catalogue was published.
        installed: bool = False

        # Track whether the installation completed.
        completed: bool = False

        # Prepare and publish the catalogue.
        try:
            # Materialize the source into the staging directory.
            source.materialize(staged_source, catalogue_dir)

            # Resolve the catalogue root inside the materialized source.
            staged_catalogue: Path = SourceLayout(staged_source).resolve(which)

            # Rewrite the manifest name when required.
            self._rewrite_manifest_name(staged_catalogue, name)

            # Validate the staged catalogue.
            staged: Catalogue = CatalogueLoader().load(staged_catalogue)

            # If the validated name differs from the requested name.
            if staged.name != name:
                # Throw.
                raise CatalogueInstallError(f"Catalogue manifest `{manifest_path(staged_catalogue)}` declares the name `{staged.name}` instead of `{name}`.")

            # If an existing catalogue must be preserved.
            if catalogue_dir.exists():
                # Move the previous catalogue into the backup directory.
                os.replace(catalogue_dir, backup_catalogue)

                # Mark the backup.
                backed_up = True

            # Publish the staged catalogue.
            os.replace(staged_catalogue, catalogue_dir)

            # Mark the installation.
            installed = True

            # Publish the registration after the catalogue files.
            self.store.register(name, source.origin, force, replace = os.replace)

            # Mark the completion.
            completed = True

        # If installation fails.
        except Exception:
            # Remove the newly installed catalogue.
            if installed:
                # Delete the partial installation.
                shutil.rmtree(catalogue_dir)

            # If a backup exists.
            if backed_up:
                # Restore the previous catalogue.
                os.replace(backup_catalogue, catalogue_dir)

            # Propagate the original failure.
            raise

        # Remove the staging directory after success or rollback.
        finally:
            # If the installation completed or no backup remains.
            if completed or not backup_catalogue.exists():
                # Delete the staging directory.
                shutil.rmtree(staging_dir)

        # Return the installed catalogue directory.
        return catalogue_dir

    # Rewrite a staged manifest name while preserving its comments.
    def _rewrite_manifest_name(self: "CatalogueInstaller", catalogue_dir: Path, name: str) -> None:
        # Compute the manifest path.
        manifest_file: Path = manifest_path(catalogue_dir)

        # Read and parse the manifest.
        try:
            # Parse the manifest while preserving formatting.
            document: tomlkit.TOMLDocument = tomlkit.parse(manifest_file.read_text(encoding = "utf-8"))

        # If the manifest cannot be read or parsed.
        except (OSError, UnicodeDecodeError, TOMLKitError) as error:
            # Throw.
            raise CatalogueInstallError(f"Unable to rewrite the catalogue manifest `{manifest_file}`: {error}") from error

        # Get the catalogue metadata.
        catalogue: object = document.get("catalogue")

        # If the catalogue metadata is not a table.
        if not isinstance(catalogue, MutableMapping):
            # Throw.
            raise CatalogueInstallError(f"Catalogue manifest `{manifest_file}` is missing a `[catalogue]` table.")

        # If the manifest name already matches.
        if catalogue.get("name") == name:
            # Return without rewriting.
            return

        # Rewrite the catalogue name.
        catalogue["name"] = name

        # Write the updated manifest.
        manifest_file.write_text(tomlkit.dumps(document), encoding = "utf-8")

    # Initialize the installer.
    def __init__(self: "CatalogueInstaller", home: Path, store: ConfigurationStore | None = None) -> None:
        # Bind and retain the configuration store.
        self.store = store if store is not None else ConfigurationStore(home.expanduser().resolve())

    # Install one catalogue source under the requested name.
    def install(self: "CatalogueInstaller", name: str, source: CatalogueSource, *, which: str | None = None, force: bool = False) -> Path:
        # Wrap expected filesystem failures in a domain error.
        try:
            # Install the catalogue and publish its files and registration.
            return self._install(name, source, which = which, force = force)

        # If the filesystem cannot complete the installation.
        except (OSError, shutil.Error) as error:
            # Throw.
            raise CatalogueInstallError(f"Unable to install catalogue `{name}`: {error}") from error
