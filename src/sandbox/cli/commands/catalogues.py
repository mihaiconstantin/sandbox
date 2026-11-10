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


# Create the catalogue command registered under the `create` group.
@click.command(name = "catalogue")
@click.argument(
    "name",
    type = str,
    callback = catalogue_argument,
    help = "The name of the catalogue to create.",
)
@click.option(
    "--source",
    type = str,
    required = False,
    default = BUNDLED_CATALOGUE_SOURCE,
    show_default = True,
    help = "The catalogue source can be \"bundled\", a local directory, or a `git` URL.",
)
@home_option()
@click.option(
    "-f", "--force",
    is_flag = True,
    default = False,
    help = "Replace an existing catalogue regardless of its origin.",
)
@click.option(
    "-y", "--yes",
    is_flag = True,
    default = False,
    help = "Skip the replacement confirmation prompt.",
)
@click.pass_context
def create_catalogue(ctx: click.Context, name: str, source: str, home: Path, force: bool, yes: bool) -> None:
    """Install a `sandbox` catalogue of development recipes."""

    # Resolve the client for the selected home.
    client: SandboxClient = client_for(ctx, home)

    # Report whether the catalogue is already registered or present.
    state: CatalogueInstallState = client.catalogues.installation(name)

    # Determine whether the catalogue directory or registration exists.
    exists: bool = state.directory_present or state.registered

    # If a forced replacement would overwrite an existing catalogue without confirmation.
    if force and exists and not yes:
        # Warn that local modifications will be overwritten.
        click.secho("Existing catalogue files and local modifications will be replaced.", fg = "red", bold = True, color = ctx.color)

        # Require explicit confirmation.
        click.confirm("Are you sure you want to replace the existing catalogue?", default = False, abort = True)

    # User feedback.
    click.secho(f"Installing catalogue `{name}`...", fg = "yellow", italic = True, color = ctx.color)

    # Install the catalogue under the requested name, replacing it only when requested.
    installed_dir: Path = client.catalogues.install(name, source, force = force)

    # User feedback.
    click.secho(f"Successfully installed catalogue `{name}` at `{installed_dir}`.", fg = "green", bold = True, color = ctx.color)


# Create the catalogue command registered under the `edit` group.
@click.command(name = "catalogue")
@click.argument(
    "name",
    type = str,
    callback = catalogue_argument,
    help = "The name of the registered catalogue to edit.",
)
@home_option()
@click.pass_context
def edit_catalogue(ctx: click.Context, name: str, home: Path) -> None:
    """Edit a registered catalogue in your editor.

    The catalogue directory is opened with `$VISUAL` or `$EDITOR`. The editor
    must block until it is closed so the catalogue can be validated afterwards.
    """

    # Resolve the client for the selected home.
    client: SandboxClient = client_for(ctx, home)

    # Resolve the registered catalogue to its managed directory.
    catalogue_dir: Path = _locate(client, name)

    # User feedback.
    click.secho(f"Editing catalogue `{name}` at `{catalogue_dir}`.", italic = True, color = ctx.color)
    click.secho("Reinstalling this catalogue with `--force` replaces local changes.", fg = "yellow", italic = True, color = ctx.color)

    # Open the catalogue directory in the configured editor.
    click.edit(filename = catalogue_dir)

    # Validate the edited catalogue with the same rules used during installation.
    client.catalogues.validate(name)

    # User feedback.
    click.secho(f"Catalogue `{name}` is valid.", fg = "green", bold = True, color = ctx.color)


# Create the catalogue command registered under the `list` group.
@click.command(name = "catalogues")
@home_option()
@click.pass_context
def catalogues(ctx: click.Context, home: Path) -> None:
    """List all registered `sandbox` catalogues."""

    # Load the catalogue registrations through the SDK.
    registrations: tuple[CatalogueRegistration, ...] = client_for(ctx, home).catalogues.list()

    # If no catalogues are registered.
    if not registrations:
        # Report the empty state on stdout.
        click.secho("No catalogues registered.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Define the compatibility table columns.
    headers: tuple[str, ...] = ("NAME", "TYPE", "PATH")

    # Prepare the table rows in registration order.
    rows: list[tuple[str, ...]] = [
        (registration.name, registration.type, str(registration.path))
        for registration in registrations
    ]

    # Display the catalogues as a plain table.
    TableRenderer().render(headers, rows, color = ctx.color)


# Create the recipes command registered under the `list` group.
@click.command(name = "recipes")
@click.option(
    "-c", "--catalogue",
    type = str,
    required = True,
    callback = catalogue_argument,
    help = "The registered catalogue whose recipes to list.",
)
@home_option()
@click.pass_context
def recipes(ctx: click.Context, catalogue: str, home: Path) -> None:
    """List the recipes declared by a registered `sandbox` catalogue."""

    # Load the recipe declarations through the SDK.
    listings: tuple[RecipeListing, ...] = client_for(ctx, home).catalogues.recipes(catalogue)

    # Define the compatibility table columns.
    headers: tuple[str, ...] = ("NAME", "DEFAULT")

    # Prepare rows in name order, marking the declared default recipe.
    rows: list[tuple[str, ...]] = [
        (listing.name, "yes" if listing.is_default else "")
        for listing in listings
    ]

    # Display the recipes as a plain table.
    TableRenderer().render(headers, rows, color = ctx.color)


# Create the catalogue command registered under the `remove` group.
@click.command(name = "catalogue")
@click.argument(
    "name",
    type = str,
    callback = catalogue_argument,
    help = "The name of the registered catalogue to remove.",
)
@home_option()
@click.option(
    "-y", "--yes",
    is_flag = True,
    default = False,
    help = "Skip the removal confirmation prompt.",
)
@click.pass_context
def remove_catalogue(ctx: click.Context, name: str, home: Path, yes: bool) -> None:
    """Remove a registered catalogue, its registration, and its secret bindings."""

    # Resolve the client for the selected home.
    client: SandboxClient = client_for(ctx, home)

    # Plan the removal without changing anything.
    plan: CatalogueRemovalPlan | None = client.catalogues.plan_removal(name)

    # If the catalogue is not registered.
    if plan is None:
        # Report the skip on stdout.
        click.secho(f"Skipped removing catalogue `{name}` because it is not registered.", fg = "yellow", color = ctx.color)

        # Return.
        return

    # Display the catalogue scheduled for removal.
    click.secho(f"\nRemoving catalogue `{plan.registration.name}`...", fg = "yellow", italic = True, color = ctx.color)

    # Display the catalogue metadata.
    click.secho("\nCatalogue", bold = True, color = ctx.color)
    click.echo(f"  Name       {plan.registration.name}")
    click.echo(f"  Type       {plan.registration.type}")

    # Create the directory suffix.
    directory_suffix: str = "" if plan.registration.path.exists() else " (missing)"

    # Display the catalogue directory.
    click.echo(f"  Directory  {plan.registration.path}{directory_suffix}")

    # Display the catalogue-scoped secret bindings.
    click.secho("\nSecret bindings", bold = True, color = ctx.color)

    # If the catalogue has secret bindings.
    if plan.registration.bindings:
        # Declare the binding.
        binding: CatalogueBinding

        # For each binding.
        for binding in plan.registration.bindings:
            # Display only the binding alias and host path.
            click.echo(f"  {binding.alias} -> {binding.path}")
    # Otherwise.
    else:
        # Display none.
        click.echo("  None")

    # Display the catalogue files to be deleted.
    click.secho("\nFiles", bold = True, color = ctx.color)

    # If the catalogue directory exists.
    if plan.registration.path.exists():
        # Display that the catalogue files will be deleted.
        click.echo("  will be deleted")
    # Otherwise.
    else:
        # Display that the catalogue files are already missing.
        click.echo("  already missing")

    # Separate the plan from the warning.
