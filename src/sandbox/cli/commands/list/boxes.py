# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.context import client_for
from sandbox.cli.presentation.table import TableRenderer

# Import the observed box value.
from sandbox.domain import BoxObservation


# List all managed boxes.
@click.command(name = "boxes")
@click.pass_context
def boxes(ctx: click.Context) -> None:
    """List all `sandbox` boxes."""

    # List the observations through the SDK.
    box_list: tuple[BoxObservation, ...] = client_for(ctx).boxes.list()

    # If no boxes exist.
    if not box_list:
        # Report the empty state on stdout.
        click.secho("No `sandbox`-managed boxes found.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Define the compatibility table columns.
    headers: tuple[str, ...] = ("PROJECT", "STATUS", "IMAGE", "WORKING DIRECTORY")

    # Map each observation with explicit unavailable fallbacks.
    rows: list[tuple[str, ...]] = [
        (
            box.name,
            box.status_text if box.status_text is not None else "unknown",
            box.image if box.image is not None else "unknown",
            box.working_directory if box.working_directory is not None else "unknown",
        )
        for box in box_list
    ]

    # Display the boxes as a plain table.
    TableRenderer().render(headers, rows, color = ctx.color)


# Define the public API of the `sandbox.cli.commands.list.boxes` module.
__all__: list[str] = ["boxes"]
