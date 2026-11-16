# Imports.
import shutil
from pathlib import Path

# Import the source interface.
from sandbox.catalogue.sources.source import CatalogueSource

# Import the registry origin.
from sandbox.configuration import registry

# Import errors.
from sandbox.errors.catalogues import CatalogueInstallError


# Represent one catalogue copied from a local directory.
class LocalCatalogueSource(CatalogueSource):
    # Local source path.
    source: Path

    # Registry origin.
    origin: str

    # Reject a source that overlaps the final catalogue destination.
    def _validate_path_separation(self: "LocalCatalogueSource", source: Path, destination: Path) -> None:
        # Resolve the destination path.
        resolved_destination: Path = destination.expanduser().resolve()

        # Resolve the source path.
        resolved_source: Path = source.expanduser().resolve()

        # If either path contains the other.
        if resolved_source == resolved_destination or resolved_source.is_relative_to(resolved_destination) or resolved_destination.is_relative_to(resolved_source):
            # Throw.
            raise CatalogueInstallError(f"Catalogue source `{resolved_source}` overlaps the catalogue destination `{resolved_destination}`.")

    # Initialize the local source.
    def __init__(self: "LocalCatalogueSource", value: str) -> None:
        # If no source path was provided.
        if not value:
            # Throw.
            raise CatalogueInstallError("A local catalogue source path is required.")

        # Expand and resolve the source path.
        source: Path = Path(value).expanduser().resolve()

        # If the source is missing or not a directory.
        if not source.is_dir():
            # Throw.
            raise CatalogueInstallError(f"Local catalogue source `{value}` is not a directory.")

        # Retain the source path and registry origin.
        self.source = source
        self.origin = registry.LOCAL_CATALOGUE_TYPE

    # Copy the local catalogue into the staging directory.
    def materialize(self: "LocalCatalogueSource", staging: Path, destination: Path) -> None:
        # Reject overlapping source and destination paths.
        self._validate_path_separation(self.source, destination)

        # Copy the source while preserving symlinks.
        shutil.copytree(self.source, staging, symlinks = True)
