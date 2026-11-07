# Imports.
from __future__ import annotations

import click

# Import the CLI helpers.
from sandbox.cli.completion import complete_running_projects
from sandbox.cli.context import client_for, cli_context
from sandbox.cli.parameters import project_argument


# Stop an existing box.
@click.command(name = "stop")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    shell_complete = complete_running_projects,
    help = "The name of the project whose box to stop.",
)
@click.pass_context
def stop(ctx: click.Context, project: str) -> None:
    """Stop a running box."""

    # Scope transient progress to the lifecycle operation.
    with cli_context(ctx).presentation.output:
        # Apply the observed-state policy through the SDK.
        stopped: bool = client_for(ctx).boxes.stop(project)

    # If the box was stopped.
    if stopped:
        # Report the success result on stdout.
        click.secho(f"Successfully stopped the box for project `{project}`.", fg = "green", bold = True, color = ctx.color)
    # Otherwise.
    else:
        # Report the preserved skip result on stdout.
        click.secho(f"Skipped stopping the box for project `{project}` because it is already stopped.", fg = "yellow", color = ctx.color)
