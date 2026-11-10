# Imports.
from __future__ import annotations

from pathlib import Path

import click

# Import the CLI helpers.
from sandbox.cli.context import client_for
from sandbox.cli.parameters import catalogue_argument, home_option
from sandbox.cli.presentation.table import TableRenderer

# Import the public registry values.
from sandbox.domain import CatalogueBinding, CatalogueRegistration, CatalogueRemovalPlan

# Import the SDK source discriminator, public result values, and registry error.
from sandbox.errors.catalogues import RegistryError
from sandbox.sdk import BUNDLED_CATALOGUE_SOURCE, CatalogueInstallState, RecipeListing, SandboxClient

# Locate a registered catalogue and add the discovery hint to its absence.
def _locate(client: SandboxClient, name: str) -> Path:
    # Resolve the registered catalogue directory.
    try:
        return client.catalogues.locate(name)

    # Add the discovery hint without changing the public error type.
    except RegistryError as error:
        # Re-raise the typed failure with the compatibility hint.
        raise RegistryError(f"{error}\nRun `sb list catalogues` to see registered catalogues.") from None
