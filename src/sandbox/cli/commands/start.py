# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.completion import complete_exited_projects
from sandbox.cli.context import client_for, cli_context
from sandbox.cli.parameters import project_argument


# Start an existing box.
@click.command(name = "start")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    shell_complete = complete_exited_projects,
    help = "The name of the project whose box to start.",
)
@click.pass_context
def start(ctx: click.Context, project: str) -> None:
    """Start a stopped box."""

    # Scope transient progress to the lifecycle operation.
    with cli_context(ctx).presentation.output:
        # Apply the observed-state policy through the SDK.
        started: bool = client_for(ctx).boxes.start(project)

    # If the box was started.
    if started:
        # Report the success result on stdout.
        click.secho(f"Successfully started the box for project `{project}`.", fg = "green", bold = True, color = ctx.color)
    # Otherwise.
    else:
        # Report the preserved skip result on stdout.
        click.secho(f"Skipped starting the box for project `{project}` because it is already running.", fg = "yellow", color = ctx.color)
