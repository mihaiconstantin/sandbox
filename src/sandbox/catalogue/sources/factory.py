# Imports.
from sandbox.catalogue.sources.git import GitCatalogueSource
from sandbox.catalogue.sources.local import LocalCatalogueSource
from sandbox.catalogue.sources.source import CatalogueSource


# Classify one catalogue source value.
def create_source(value: str) -> CatalogueSource:
    # If the value looks like a git repository.
    if "://" in value or value.startswith("git@"):
        # Return the git source.
        return GitCatalogueSource(value)

    # Otherwise.
    return LocalCatalogueSource(value)
