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


# Create the volume command registered under the `remove` group.
@click.command(name = "volume")
@click.argument(
    "name",
    type = str,
    callback = volume_argument,
    help = "The name of the managed `docker` volume to remove.",
)
@click.option(
    "-y", "--yes",
    is_flag = True,
    default = False,
    help = "Skip the removal confirmation prompt.",
)
@click.pass_context
def remove_volume(ctx: click.Context, name: str, yes: bool) -> None:
    """Remove a `sandbox`-managed `docker` volume.

    All data stored in the volume is permanently deleted. The volume must not be
    referenced by any running or stopped boxes.
    """

    # Resolve the home-bound client once for this command.
    client = client_for(ctx)

    # Inspect the requested volume through the SDK.
    volume_info: VolumeInfo | None = client.volumes.get(name)

    # If the volume does not exist.
    if volume_info is None:
        # Report the preserved absence skip on stdout.
        click.secho(f"Skipped removing the `docker` volume `{name}` because it does not exist.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Display the volume metadata.
    click.secho("\nVolume", bold = True, color = ctx.color)

    # Display each metadata field.
    click.echo(f"  Name       {volume_info.name}")
    click.echo(f"  Driver     {volume_info.driver if volume_info.driver is not None else 'unknown'}")
    click.echo(f"  Mountpoint {volume_info.mountpoint if volume_info.mountpoint is not None else 'unknown'}")

    # Display containers referencing the volume.
    click.secho("\nReferencing containers", bold = True, color = ctx.color)

    # If the reference set cannot be established.
    if volume_info.in_use_by is None:
        # Display the unknown reference count.
        click.echo("  ?")

        # Refuse removal rather than guessing.
        raise VolumeReferencesUnavailable(name)

    # If no containers reference the volume.
    if not volume_info.in_use_by:
        # Display none.
        click.echo("  None")

    # For each container referencing the volume.
    for container in volume_info.in_use_by:
        # Display the container name.
        click.echo(f"  {container.name}")

    # If the volume is still referenced by containers.
    if volume_info.in_use_by:
        # Refuse removal.
        raise VolumeInUse(name)

    # Warn that the volume's data will be permanently deleted.
    click.secho("\nAll data stored in this volume will be permanently deleted.", fg = "red", bold = True, color = ctx.color)

    # If no explicit confirmation was provided via the `--yes` flag.
