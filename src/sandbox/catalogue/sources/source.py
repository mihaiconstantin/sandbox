# Imports.
from pathlib import Path
from typing import Protocol


# Define a materializable catalogue source.
class CatalogueSource(Protocol):
    # Registry origin of the source.
    origin: str

    # Materialize the source into a staging directory.
    def materialize(self: "CatalogueSource", staging: Path, destination: Path) -> None: ...
