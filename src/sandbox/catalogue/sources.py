# Imports.
import os
import shutil
import signal
import subprocess
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

from sandbox.configuration import registry

# Import errors and helpers.
from sandbox.errors.catalogues import CatalogueInstallError
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Define the fixed timeout for cloning a `git` catalogue.
GIT_CLONE_TIMEOUT: int = 120

# Define the supported `git` URL schemes.
GIT_URL_SCHEMES: frozenset[str] = frozenset({"https", "http", "ssh", "git", "file"})


# Reject a source that overlaps the final catalogue destination.
def _require_disjoint(source: Path, destination: Path) -> None:
    # Resolve both paths without requiring either to exist.
    resolved_source: Path = source.expanduser().resolve()
    resolved_destination: Path = destination.expanduser().resolve()

    # If either path contains the other.
    if resolved_source == resolved_destination or resolved_source.is_relative_to(resolved_destination) or resolved_destination.is_relative_to(resolved_source):
        # Throw.
        raise CatalogueInstallError(f"Catalogue source `{resolved_source}` overlaps the catalogue destination `{resolved_destination}`.")


# Kill a clone process group and reap its process.
def _terminate_clone(process: subprocess.Popen[bytes]) -> None:
    # Kill the clone process group so child network processes stop.
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    # If the process group already exited.
    except ProcessLookupError:
        pass

    # Reap the clone process.
    process.communicate()


# Describe a catalogue source that can be materialized into a destination.
class CatalogueSource(Protocol):
    # The origin recorded in the catalogue registry.
    origin: str

    # Copy the source, staging it before the final catalogue destination.
    def materialize(self, staging: Path, destination: Path) -> None: ...


# Represent the catalogue bundled with `sandbox`.
class BundledSource:
    # Record the bundled origin.
    origin: str = registry.BUNDLED_CATALOGUE_TYPE

    # Locate the bundled catalogue.
    def __init__(self) -> None:
        # Locate the bundled catalogue inside the installed package.
        source: Traversable = resources.files("sandbox").joinpath(*registry.DEFAULT_CATALOGUE_PATH.split("/"))

        # If the package catalogue is missing, use the repository layout.
        if not source.is_dir():
            source = Path(__file__).resolve().parents[3] / registry.DEFAULT_CATALOGUE_PATH

        # If the bundled catalogue does not exist.
        if not source.is_dir():
            # Throw.
            raise CatalogueInstallError(f"Bundled catalogue `{registry.DEFAULT_CATALOGUE_NAME}` was not found.")

        # Retain the located catalogue.
        self._source: Traversable = source

    # Copy the bundled catalogue into the staging directory.
    def materialize(self, staging: Path, destination: Path) -> None:
        # Copy the bundled catalogue from its package or repository location.
        with resources.as_file(self._source) as source_dir:
            # Reject a source that overlaps the final catalogue destination.
            _require_disjoint(source_dir, destination)

            # Copy the bundled catalogue.
            shutil.copytree(source_dir, staging)
