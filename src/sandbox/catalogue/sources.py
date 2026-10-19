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


# Represent a catalogue copied from a local directory.
class LocalSource:
    # Record the local origin.
    origin: str = registry.LOCAL_CATALOGUE_TYPE

    # Resolve and validate the local catalogue directory.
    def __init__(self, value: str) -> None:
        # If no source path was provided.
        if not value:
            # Throw.
            raise CatalogueInstallError("A local catalogue source path is required.")

        # Expand and resolve the source path relative to the current directory.
        source: Path = Path(value).expanduser().resolve()

        # If the source is missing or not a directory.
        if not source.is_dir():
            # Throw.
            raise CatalogueInstallError(f"Local catalogue source `{value}` is not a directory.")

        # Retain the resolved source.
        self._source: Path = source

    # Copy the local catalogue into the staging directory.
    def materialize(self, staging: Path, destination: Path) -> None:
        # Reject a source that overlaps the final catalogue destination.
        _require_disjoint(self._source, destination)

        # Copy the local catalogue while preserving symlinks.
        shutil.copytree(self._source, staging, symlinks = True)


# Represent a catalogue cloned from a `git` repository.
class GitSource:
    # Record the `git` origin.
    origin: str = registry.GIT_CATALOGUE_TYPE

    # Validate the source and retain the repository URL.
    def __init__(self, value: str) -> None:
        # If the URL uses the unsupported `git+` prefix.
        if value.startswith("git+"):
            # Throw.
            raise CatalogueInstallError("The `git+` prefix is not supported. Pass the `git` URL directly.")

        # If the URL declares a scheme.
        if "://" in value:
            # Get the declared scheme.
            scheme: str = value.split("://", 1)[0].lower()

            # If the scheme is unsupported.
            if scheme not in GIT_URL_SCHEMES:
                # Throw.
                raise CatalogueInstallError(f"Unsupported `git` URL scheme `{scheme}://`. Use HTTPS, HTTP, SSH, `git`, file, or an SCP-style URL.")

        # If the `git` executable is missing.
        if shutil.which("git") is None:
            # Throw the actionable host prerequisite.
            raise PrerequisiteError(
                "git",
                PrerequisiteKind.MISSING,
                operation = "catalogue.install",
                hint = "Install git and ensure it is on PATH.",
            )

        # Record the requested URL.
        self._url: str = value

    # Clone the repository into the staging directory.
    def materialize(self, staging: Path, destination: Path) -> None:
        # Prepare a non-interactive `git` environment.
        environment: dict[str, str] = dict(os.environ)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GCM_INTERACTIVE"] = "never"
        environment["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
        environment["GIT_ASKPASS"] = "false"
        environment["SSH_ASKPASS"] = "false"

        # Start the clone in its own session so it has no controlling terminal.
        try:
            # Launch the non-interactive clone.
            process: subprocess.Popen[bytes] = subprocess.Popen(
                ["git", "clone", "--depth", "1", "--", self._url, str(staging)],
                stdin = subprocess.DEVNULL,
                stdout = subprocess.DEVNULL,
                stderr = subprocess.DEVNULL,
                env = environment,
                start_new_session = True,
            )

        # If the `git` executable cannot be launched.
        except OSError as error:
            # Classify a vanished executable separately from an unusable installation.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Throw the actionable host prerequisite.
            raise PrerequisiteError(
                "git",
                kind,
                operation = "catalogue.install",
                diagnostic = str(error)[:4096],
                hint = "Ensure the `git` executable can run and retry.",
            ) from error

        # Wait for the clone and enforce the timeout.
        try:
            process.communicate(timeout = GIT_CLONE_TIMEOUT)

        # If the clone exceeds the timeout.
        except subprocess.TimeoutExpired:
            # Stop the clone process tree before reporting the timeout.
            _terminate_clone(process)

            # Throw.
            raise CatalogueInstallError(f"`git` clone timed out after {GIT_CLONE_TIMEOUT} seconds.") from None

        # If the user interrupts the clone.
        except KeyboardInterrupt:
            # Stop the clone process tree before propagating the interruption.
            _terminate_clone(process)

            # Propagate the interruption.
            raise

        # If the clone fails.
        if process.returncode != 0:
            # Throw without exposing the URL or the `git` output.
            raise CatalogueInstallError(f"`git` clone failed with exit code {process.returncode}.")


# Build the catalogue source for a CLI value.
def source_for(value: str) -> CatalogueSource:
    # If the value selects the bundled catalogue.
    if value == registry.BUNDLED_CATALOGUE_TYPE:
        # Return the bundled source.
        return BundledSource()

    # If the value looks like a `git` repository.
    if "://" in value or value.startswith("git@"):
        # Return the `git` source.
        return GitSource(value)

    # Otherwise, treat the value as a local directory.
    return LocalSource(value)
