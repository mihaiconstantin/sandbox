# Imports.
import os
import tempfile
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

# Import typed configuration errors.
from sandbox.errors.catalogues import RegistryError

# Define the permission bits used for a newly created registry before the umask.
DEFAULT_REGISTRY_BITS: int = 0o666


# Compute the mode a regular file receives under the current process umask.
def default_file_mode() -> int:
    # Read and restore the process umask.
    current: int = os.umask(0)
    os.umask(current)

    # Apply the umask to the default file bits.
    return DEFAULT_REGISTRY_BITS & ~current


# Load and parse a catalogue registry without exposing read, decode, or parser errors.
def load_document(document_file: Path) -> tomlkit.TOMLDocument:
    # Read the registry content.
    try:
        content: str = document_file.read_text(encoding = "utf-8")

    # If the registry does not exist.
    except FileNotFoundError:
        # Throw.
        raise RegistryError(f"Catalogue registry `{document_file}` does not exist.") from None

    # If the registry is not UTF-8 encoded.
    except UnicodeDecodeError:
        # Throw.
        raise RegistryError(f"Catalogue registry `{document_file}` must be UTF-8 encoded.") from None

    # If the registry cannot be read.
    except OSError as error:
        # Throw with the reason rather than the raw operating-system exception.
        raise RegistryError(f"Unable to read catalogue registry `{document_file}`: {error.strerror or error}.") from error

    # Parse the native TOML document.
    try:
        return tomlkit.parse(content)

    # If the registry is malformed.
    except TOMLKitError as error:
        # Throw.
        raise RegistryError(f"Unable to parse catalogue registry `{document_file}`: {error}") from error


# Write a catalogue registry atomically.
def write_document_atomic(
    document_file: Path,
    document: tomlkit.TOMLDocument,
    replace: Any = None,
    *,
    new_mode: int | None = None,
) -> None:
    # Determine the existing file mode when available.
    try:
        mode: int | None = document_file.stat().st_mode & 0o777

    # If the registry does not exist.
    except FileNotFoundError:
        mode = new_mode

    # Create a temporary file in the registry directory.
    descriptor: int
    temporary_name: str
    descriptor, temporary_name = tempfile.mkstemp(prefix = f".{document_file.name}.", suffix = ".tmp", dir = document_file.parent)
    temporary_file: Path = Path(temporary_name)

    # Write the registry through the temporary file.
