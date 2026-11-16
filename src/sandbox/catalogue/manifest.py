# Imports.
from pathlib import Path

# Define the manifest filename expected in every catalogue.
CATALOGUE_MANIFEST_FILENAME: str = "catalogue.toml"


# Compute the manifest path inside one catalogue directory.
def manifest_path(directory: Path) -> Path:
    # Return the manifest path.
    return directory / CATALOGUE_MANIFEST_FILENAME
