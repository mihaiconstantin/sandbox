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
