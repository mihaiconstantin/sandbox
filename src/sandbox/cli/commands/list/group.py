# Imports.
from __future__ import annotations

import click

# Import the list resource commands.
from sandbox.cli.commands.list.boxes import boxes
from sandbox.cli.commands.list.volumes import volumes


# Group the `sandbox` list commands.
@click.group(name = "list")
def list_resources() -> None:
    """List `sandbox` development resources."""
