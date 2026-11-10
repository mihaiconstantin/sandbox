# Imports.
from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any, NoReturn

import click

# Import the SDK-backed commands.
from sandbox.cli.commands.completions import completions
from sandbox.cli.commands.create import create_group
from sandbox.cli.commands.enter import enter
from sandbox.cli.commands.list import list_resources
from sandbox.cli.commands.start import start
from sandbox.cli.commands.status import status
from sandbox.cli.commands.stop import stop

# Import the CLI context and presentation.
from sandbox.cli.context import CliContext, ClientFactory, cli_context
from sandbox.cli.presentation.help import apply_styled_context, configure_help

# Import the public error root.
from sandbox.errors import SandboxError


# Present one public error through the single injected presenter.
def present_error(ctx: click.Context, error: SandboxError) -> NoReturn:
    # Read the per-invocation context once.
    context: CliContext = cli_context(ctx)

    # Suspend transient status before writing the durable error line.
    context.presentation.close()

    # Present through the invoked context's presenter.
    context.errors.present(error)


# Route the public error family through the single presenter from Click invoke.
class SandboxGroup(click.Group):
    # Catch public failures from the group and every subcommand.
    def invoke(self, ctx: click.Context) -> object:
        # Run normal Click dispatch and finalize transient presentation.
        try:
            # Run the normal command path.
            try:
                # Delegate the invocation.
                return super().invoke(ctx)

            # Present expected public failures in one place.
            except SandboxError as error:
                # Render on stderr and exit with the documented class.
                present_error(ctx, error)

        # Finalize transient status and child decoding for this invocation.
        finally:
            # Stop any active status line without replacing an earlier failure.
            cli_context(ctx).presentation.close()


# Root CLI group for the application commands.
@click.group(cls = SandboxGroup)
@click.version_option(package_name = "sandbox", message = "%(version)s")
def cli() -> None:
    """
    `sandbox` (`sb`) is a tool for managing isolated development environments.
    """


# Configure the styled help text and epilog.
configure_help(cli)


# Create the integration-owned `edit` command group shell.
@click.group(name = "edit")
def edit_group() -> None:
    """Edit a `sandbox` resource."""


# Create the integration-owned `remove` command group shell.
@click.group(name = "remove")
def remove_group() -> None:
    """Remove a `sandbox` resource."""





# Register the SDK-backed read and lifecycle commands.
cli.add_command(completions)
cli.add_command(enter)
cli.add_command(list_resources)
cli.add_command(start)
cli.add_command(status)
cli.add_command(stop)

# Register the resource-group registration points for later slices.
cli.add_command(create_group)
cli.add_command(edit_group)
cli.add_command(remove_group)


# Apply the deterministic help context to the group and every registered command.
apply_styled_context(cli)
