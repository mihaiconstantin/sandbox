# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.context import client_for, cli_context
from sandbox.cli.parameters import volume_argument

# Import the observed volume values.
from sandbox.domain import EnsuredVolume, VolumeInfo

# Import the typed reference failures.
from sandbox.errors.volumes import VolumeInUse, VolumeReferencesUnavailable


# Create the volume command registered under the `create` group.
@click.command(name = "volume")
@click.argument(
    "name",
    type = str,
    callback = volume_argument,
    help = "The name of the volume to create.",
)
@click.pass_context
def create_volume(ctx: click.Context, name: str) -> None:
    """Create a shared, `sandbox`-managed `docker` volume."""

    # Scope transient progress to the SDK operation.
    with cli_context(ctx).presentation.output:
        # Ensure the volume and read whether this call created it.
        ensured: EnsuredVolume = client_for(ctx).volumes.ensure(name)

    # If the volume was created.
    if ensured.created:
        # Report the success result on stdout.
        click.secho(f"Successfully created a `docker` volume named `{name}`.", fg = "green", bold = True, color = ctx.color)
    # Otherwise.
    else:
        # Report the preserved skip result on stdout.
        click.secho(f"Skipped creating the `docker` volume `{name}` because it already exists.", fg = "yellow", color = ctx.color)
