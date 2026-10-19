"""Verify the bundled catalogue assets agree with its declared secret requirements."""

# Imports.
from __future__ import annotations

import re
from pathlib import Path

# Import the manifest loader for the bundled catalogue.
from sandbox.catalogue.manifest import load_catalogue

# Locate the bundled catalogue in the repository.
CATALOGUE_ROOT: Path = Path(__file__).resolve().parents[1] / "catalogues" / "default"


# Verify the bundled aliases read only secrets that a bundled recipe declares.
def test_bundled_aliases_read_only_declared_secrets() -> None:
    # Load the bundled manifest and collect every declared secret alias.
    catalogue = load_catalogue(CATALOGUE_ROOT)
    declared: set[str] = {
        alias
        for recipe in catalogue.recipes.values()
        for alias in recipe.secrets
    }

    # Read the bundled aliases script.
    script: str = (CATALOGUE_ROOT / "scripts" / "aliases.sh").read_text(encoding = "utf-8")

    # Extract every secret alias the script reads from the guest secret root.
    read: set[str] = set(re.findall(r"/run/secrets/([A-Za-z0-9_.-]+)", script))

    # Require the script to exercise at least one secret.
    assert read, "The bundled aliases script must read a declared secret."

    # Require every secret read by the script to be declared by the catalogue.
    assert read <= declared, f"The bundled aliases script reads undeclared secrets: {sorted(read - declared)}"
