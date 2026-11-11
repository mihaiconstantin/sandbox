# Imports.
from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any, NoReturn

import click

# Import the SDK-backed commands.
from sandbox.cli.commands.boxes import create_box, remove_box
from sandbox.cli.commands.catalogues import create_catalogue, edit_catalogue, remove_catalogue
from sandbox.cli.commands.completions import completions
from sandbox.cli.commands.create import create_group
from sandbox.cli.commands.enter import enter
from sandbox.cli.commands.list import list_resources
from sandbox.cli.commands.secrets import create_secret, remove_secret
from sandbox.cli.commands.start import start
from sandbox.cli.commands.status import status
from sandbox.cli.commands.stop import stop
from sandbox.cli.commands.volumes import create_volume, remove_volume

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


# Run the CLI with the single presenter as the outer guard.
def main(
    context: CliContext | ClientFactory | None = None,
    *,
    console: Any | None = None,
    args: Sequence[str] | None = None,
) -> None:
    # Disable traceback for expected failures.
    sys.tracebacklimit = 0

    # Resolve an explicit presentation context, a factory, or production defaults.
    selected: CliContext
    if isinstance(context, CliContext):
        # Use the caller-supplied context unchanged.
        selected = context
    elif context is not None:
        # Wrap a composition-supplied factory with presentation defaults.
        selected = CliContext.create(client_factory = context, console = console)
    else:
        # Build the inert default context without a factory.
        selected = CliContext.create(console = console)

    # Run the normal Click entry point and present any public error escaping invoke.
    try:
        # Delegate normal Click error handling with the injected context.
        cli.main(args = args, obj = selected)

    # Present an expected public failure that bypassed Click dispatch.
    except SandboxError as error:
        # Render on stderr and exit with the documented class.
        selected.errors.present(error)


# If the script is run directly.
if __name__ == "__main__":
    # Run the CLI with the single error presenter.
    main()


# Define the public API of the `sandbox.cli.group` module.
__all__: list[str] = ["SandboxGroup", "cli", "create_group", "edit_group", "main", "present_error", "remove_group"]
