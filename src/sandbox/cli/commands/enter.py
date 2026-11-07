# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.completion import complete_running_projects
from sandbox.cli.context import client_for
from sandbox.cli.parameters import project_argument


# Enter a live box.
@click.command(name = "enter")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    shell_complete = complete_running_projects,
    help = "The name of the project whose box to enter.",
)
@click.option(
    "-s", "--shell",
    type = str,
    default = "zsh",
    show_default = True,
    help = "The shell to use when entering the box.",
)
@click.option(
    "-l", "--login/--no-login",
    default = True,
    help = "Start the shell as a login shell by default.",
)
@click.pass_context
def enter(ctx: click.Context, project: str, shell: str, login: bool) -> None:
    """Enter a running box."""

    # Delegate the interactive shell without SDK terminal policy.
    status: int = client_for(ctx).boxes.enter(project, shell = shell, login = login)

    # Preserve a positive shell status and normalize signals.
    if status != 0:
        # Terminate with the normalized shell status.
        raise SystemExit(status if status > 0 else 1)


# Define the public API of the `sandbox.cli.commands.enter` module.
__all__: list[str] = ["enter"]
