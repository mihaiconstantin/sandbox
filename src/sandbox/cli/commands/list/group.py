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


# Register the SDK-backed list commands.
list_resources.add_command(boxes)
list_resources.add_command(volumes)
list_resources.add_command(catalogues)
list_resources.add_command(recipes)
list_resources.add_command(secrets)


# Define the public API of the `sandbox.cli.commands.list.group` module.
__all__: list[str] = ["list_resources"]
