# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.context import client_for, cli_context
from sandbox.cli.presentation.table import TableRenderer

# Import the observed volume value.
from sandbox.domain import VolumeInfo


# List all managed shared volumes.
@click.command(name = "volumes")
@click.pass_context
def volumes(ctx: click.Context) -> None:
    """List all `sandbox`-managed `docker` volumes."""

    # List the observations through the SDK.
    volume_list: tuple[VolumeInfo, ...] = client_for(ctx).volumes.list()

    # If no volumes exist.
    if not volume_list:
        # Read the composition vocabulary for the backend tool noun.
        tool: str = cli_context(ctx).vocabulary.tool

        # Report the empty state on stdout.
        click.secho(f"No `sandbox`-managed {tool} volumes found.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Define the compatibility table columns.
    headers: tuple[str, ...] = ("NAME", "DRIVER", "CONTAINERS")

    # Map each observation with explicit unavailable fallbacks.
    rows: list[tuple[str, ...]] = [
        (
            volume.name,
            volume.driver if volume.driver is not None else "unknown",
            str(len(volume.in_use_by)) if volume.in_use_by is not None else "?",
        )
        for volume in volume_list
    ]

    # Display the volumes as a plain table.
    TableRenderer().render(headers, rows, color = ctx.color)


# Define the public API of the `sandbox.cli.commands.list.volumes` module.
__all__: list[str] = ["volumes"]
