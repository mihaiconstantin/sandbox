# Imports.
from __future__ import annotations

import click

# Import the list resource commands.
from sandbox.cli.commands.catalogues import catalogues, recipes
from sandbox.cli.commands.list.boxes import boxes
from sandbox.cli.commands.list.volumes import volumes
from sandbox.cli.commands.secrets import secrets


# Group the `sandbox` list commands.
@click.group(name = "list")
def list_resources() -> None:
    """List `sandbox` development resources."""
