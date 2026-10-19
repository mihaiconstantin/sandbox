# Imports.
import os
import shutil
import tempfile
from collections.abc import MutableMapping
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from sandbox.catalogue import manifest, sources

# Import models.
from sandbox.catalogue.catalogue import Catalogue
from sandbox.configuration.store import ConfigurationStore

# Import errors and helpers.
from sandbox.errors.catalogues import CatalogueInstallError


# Install catalogues below the `sandbox` catalogue root.
class CatalogueInstaller:
    # Prepare an installer for a `sandbox` directory.
    def __init__(self, home: Path, store: ConfigurationStore | None = None) -> None:
        # Resolve the `sandbox` directory.
        self.home: Path = home.expanduser().resolve()

        # Bind the installer to the configuration store.
        self.store: ConfigurationStore = store if store is not None else ConfigurationStore(self.home)

    # Install and publish a catalogue under the requested name.
    def _install(self, name: str, source: sources.CatalogueSource, force: bool = False) -> Path:
        # Compute the catalogue destination, validating the name.
        catalogue_dir: Path = self.store.destination(name)

        # Determine whether the catalogue directory already exists.
        directory_exists: bool = catalogue_dir.exists() or catalogue_dir.is_symlink()

        # Determine whether the catalogue is already registered.
        registered: bool = any(item.name == name for item in self.store.registrations())

        # If an existing catalogue would be replaced without permission.
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

        # Create a temporary directory for staging and backup.
        staging_dir: Path = Path(tempfile.mkdtemp(prefix = f".{name}-", dir = catalogue_dir.parent))

        # Prepare paths for the staged catalogue and the previous installation.
        staged_catalogue: Path = staging_dir / "catalogue"


# Install a catalogue from a source value.
def install_catalogue(home: Path, name: str, source: str, force: bool = False) -> Path:
    # Build the catalogue installer and source.
    installer: CatalogueInstaller = CatalogueInstaller(home)
    catalogue_source: sources.CatalogueSource = sources.source_for(source)

    # Install the catalogue.
    return installer.install(name, catalogue_source, force)


# Rewrite a staged catalogue manifest name while preserving its comments.
def _rewrite_manifest_name(manifest_file: Path, name: str) -> None:
    # Read and parse the manifest while preserving its formatting.
    try:
        document: tomlkit.TOMLDocument = tomlkit.parse(manifest_file.read_text(encoding = "utf-8"))

    # If the manifest cannot be read or parsed.
    except (OSError, UnicodeDecodeError, TOMLKitError) as error:
        # Throw.
        raise CatalogueInstallError(f"Unable to rewrite the catalogue manifest `{manifest_file}`: {error}") from error

    # Get the catalogue metadata.
    catalogue = document.get("catalogue")

    # If the catalogue metadata is not a table.
    if not isinstance(catalogue, MutableMapping):
        # Throw.
        raise CatalogueInstallError(f"Catalogue manifest `{manifest_file}` is missing a `[catalogue]` table.")

    # If the manifest name already matches.
    if catalogue.get("name") == name:
        # Return without rewriting the manifest.
        return

    # Rewrite the catalogue name.
    catalogue["name"] = name

    # Write the updated manifest.
    manifest_file.write_text(tomlkit.dumps(document), encoding = "utf-8")
