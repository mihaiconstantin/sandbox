# Imports.
from __future__ import annotations

from pathlib import Path

import click

# Import the CLI helpers.
from sandbox.cli.context import client_for
from sandbox.cli.parameters import catalogue_argument, home_option, secret_argument
from sandbox.cli.presentation.table import TableRenderer

# Import the public secret mount target.
from sandbox.domain import secret_target


# Create the secret command registered under the `create` group.
@click.command(name = "secret")
@click.argument(
    "secret",
    type = str,
    callback = secret_argument,
)
@click.option(
    "-f", "--file",
    type = str,
    required = True,
    help = "The path to the secret file.",
)
@click.option(
    "-c", "--catalogue",
    type = str,
    required = True,
    callback = catalogue_argument,
    help = "The catalogue containing the secret.",
)
@home_option(exists = True)
@click.pass_context
def create_secret(ctx: click.Context, secret: str, file: str, catalogue: str, home: Path) -> None:
    """Bind a secret file to a catalogue-scoped secret alias. `SECRET` represents the secret alias."""

    # Save the binding without reading the secret contents.
    binding = client_for(ctx, home).secrets.bind(catalogue, secret, Path(file))

    # User feedback naming only the alias, catalogue, and host path.
    click.secho(f"Saved secret `{secret}` in catalogue `{catalogue}` from `{binding.host_path}`.", fg = "green", bold = True, color = ctx.color)

    # Explain the runtime location without reading or exporting the secret.
    click.secho(f"Mounted read-only at `{secret_target(secret)}`.", italic = True, color = ctx.color)


# Create the secret command registered under the `list` group.
@click.command(name = "secrets")
@home_option(exists = True)
@click.pass_context
def secrets(ctx: click.Context, home: Path) -> None:
    """List all configured secret bindings."""

    # Load the bindings through the SDK.
    bindings = client_for(ctx, home).secrets.list()

    # If no bindings exist.
    if not bindings:
        # Report the empty state on stdout.
        click.secho("No secrets configured.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Define the compatibility table columns.
    headers: tuple[str, ...] = ("CATALOGUE", "SECRET", "HOST PATH", "BOX PATH")

    # Prepare the table rows with paths and aliases only.
    rows: list[tuple[str, ...]] = [
        (binding.catalogue, binding.alias, str(binding.host_path), secret_target(binding.alias))
        for binding in bindings
    ]

    # Display the bindings as a plain table.
    TableRenderer().render(headers, rows, color = ctx.color)

    # Clarify when the displayed mount paths are relevant.
    click.echo()
    click.secho("Mount paths are only relevant to boxes whose recipe declares the secret.", italic = True, color = ctx.color)
    click.secho("Run `sb status <project>` to inspect a box's actual mounts.", italic = True, color = ctx.color)
