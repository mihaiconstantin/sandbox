"""Build minimal, self-contained catalogue sources for tests."""

# Imports.
from __future__ import annotations

from pathlib import Path
from textwrap import dedent


# Define the catalogue name used by test sources.
SOURCE_NAME: str = "sample"


# Declare a commented manifest with a shared volume and two recipes.
CATALOGUE_MANIFEST: str = dedent("""\
    # Catalogue metadata.
    [catalogue]
    name = "{name}"
    version = "0.1.0"
    schema_version = 1

    # The recipe used when `--recipe` is omitted.
    default_recipe = "base"

    # Define the volumes used by the recipes in the catalogue.
    [volumes.omp]
    name = "omp-state"
    scope = "shared"
    target = "/home/example/.omp"

    # Specify the recipes available in the catalogue.
    [recipes.base]
    compose = "compose.yaml"
    service = "workspace"
    volumes = ["omp"]

    [recipes.r]
    extends = "base"
    compose = "r/compose.yaml"
    service = "workspace"
""")


# Build a minimal repository containing one catalogue per immediate child.
def write_catalogue_repository(directory: Path, names: tuple[str, ...] = ("base", "r")) -> Path:
    # Create the repository root.
    directory.mkdir(parents = True, exist_ok = True)

    # Build each child catalogue with its own manifest and recipes.
    name: str
    for name in names:
        # Build the child catalogue under its directory name.
        write_catalogue_source(directory / name, name = name)

    # Return the repository root.
    return directory


# Build a minimal valid catalogue source directory.
def write_catalogue_source(directory: Path, name: str = SOURCE_NAME) -> Path:
    # Create the source directory.
    directory.mkdir(parents = True)

    # Write the commented manifest with the requested catalogue name.
    (directory / "catalogue.toml").write_text(CATALOGUE_MANIFEST.format(name = name), encoding = "utf-8")

    # Write the base recipe's compose file.
    (directory / "compose.yaml").write_text("services: {}\n", encoding = "utf-8")

    # Write the `r` recipe's compose file.
    (directory / "r").mkdir()
    (directory / "r" / "compose.yaml").write_text("services: {}\n", encoding = "utf-8")

    # Return the source directory.
    return directory
