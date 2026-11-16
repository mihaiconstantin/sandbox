# Imports.
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import ClassVar

# Import the source interface.
from sandbox.catalogue.sources.source import CatalogueSource

# Import the registry origin.
from sandbox.configuration import registry

# Import errors.
from sandbox.errors.catalogues import CatalogueInstallError
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind


# Represent one catalogue cloned from a git repository.
class GitCatalogueSource(CatalogueSource):
    # Define the clone timeout in seconds.
    _clone_timeout: int = 30

    # Define the supported git URL schemes.
    _url_schemes: ClassVar[list[str]] = ["https", "http", "ssh", "git", "file"]

    # Repository URL.
    url: str

    # Registry origin.
    origin: str

    # Kill a clone process group and reap its process.
    def _terminate_clone(self: "GitCatalogueSource", process: subprocess.Popen[bytes]) -> None:
        # Kill the process group.
        try:
            # Kill the clone process group.
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)

        # If the process group already exited.
        except ProcessLookupError:
            # Ignore the exited group.
            pass

        # Reap the clone process.
        process.communicate()

    # Initialize the git source.
    def __init__(self: "GitCatalogueSource", value: str) -> None:
        # If the URL uses the unsupported git+ prefix.
        if value.startswith("git+"):
            # Throw.
            raise CatalogueInstallError("The `git+` prefix is not supported. Pass the `git` URL directly.")

        # If the URL declares a scheme.
        if "://" in value:
            # Get the declared scheme.
            scheme: str = value.split("://", 1)[0].lower()

            # If the scheme is unsupported.
            if scheme not in self._url_schemes:
                # Throw.
                raise CatalogueInstallError(f"Unsupported `git` URL scheme `{scheme}://`. Use `HTTPS`, `HTTP`, `SSH`, `git`, `file`, or an `SCP`-style URL.")

        # If the git executable is missing.
        if shutil.which("git") is None:
            # Throw.
            raise PrerequisiteError(
                "git",
                PrerequisiteKind.MISSING,
                operation = "catalogue.install",
                hint = "Install `git` and ensure it is on `PATH`.",
            )

        # Retain the requested URL and registry origin.
        self.url = value
        self.origin = registry.GIT_CATALOGUE_TYPE

    # Clone the repository into the staging directory.
    def materialize(self: "GitCatalogueSource", staging: Path, destination: Path) -> None:
        # Prepare a non-interactive git environment.
        environment: dict[str, str] = dict(os.environ)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GCM_INTERACTIVE"] = "never"
        environment["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
        environment["GIT_ASKPASS"] = "false"
        environment["SSH_ASKPASS"] = "false"

        # Start the clone in its own session.
        try:
            # Launch the non-interactive clone.
            process: subprocess.Popen[bytes] = subprocess.Popen(
                ["git", "clone", "--depth", "1", "--", self.url, str(staging)],
                stdin = subprocess.DEVNULL,
                stdout = subprocess.DEVNULL,
                stderr = subprocess.DEVNULL,
                env = environment,
                start_new_session = True,
            )

        # If the git executable cannot be launched.
        except OSError as error:
            # Classify the prerequisite failure.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Throw.
            raise PrerequisiteError(
                "git",
                kind,
                operation = "catalogue.install",
                diagnostic = str(error)[:4096],
                hint = "Ensure the `git` executable can run and retry.",
            ) from error

        # Wait for the clone and enforce the timeout.
        try:
            # Wait for the clone.
            process.communicate(timeout = self._clone_timeout)

        # If the clone exceeds the timeout.
        except subprocess.TimeoutExpired:
            # Stop the clone process tree.
            self._terminate_clone(process)

            # Throw.
            raise CatalogueInstallError(f"`git` clone timed out after {self._clone_timeout} seconds.") from None

        # If the user interrupts the clone.
        except KeyboardInterrupt:
            # Stop the clone process tree.
            self._terminate_clone(process)

            # Propagate the interruption.
            raise

        # If the clone fails.
        if process.returncode != 0:
            # Throw.
            raise CatalogueInstallError(f"`git` clone failed with exit code {process.returncode}.")
