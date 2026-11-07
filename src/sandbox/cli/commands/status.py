# Imports.
from __future__ import annotations

from pathlib import Path

import click

# Import the CLI context and parameter helpers.
from sandbox.cli.completion import complete_projects
from sandbox.cli.context import client_for, cli_context
from sandbox.cli.parameters import project_argument

# Import display sanitization.
from sandbox.cli.presentation.text import sanitize_value

# Import public domain observation values and guest paths.
from sandbox.domain import SECRET_ROOT, BoxObservation, Mount, Network

# Import the public box lookup error.
from sandbox.errors.base import SandboxError
from sandbox.errors.boxes import BoxNotFound


# Inspect one box and render its full compatibility report.
@click.command(name = "status")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    shell_complete = complete_projects,
    help = "The name of the project whose box to inspect.",
)
@click.option(
    "--path",
    "print_path",
    is_flag = True,
    help = "Print only the host project directory.",
)
@click.pass_context
def status(ctx: click.Context, project: str, print_path: bool) -> None:
    """Inspect the status of a box and its attached resources."""

    # Read the observation through the SDK.
    box: BoxObservation | None = client_for(ctx).boxes.get(project)

    # Render absence through the single presenter using runtime vocabulary.
    if box is None:
        # Throw the vocabulary-neutral lookup error.
        raise BoxNotFound(project, backend = cli_context(ctx).vocabulary.backend)

    # If only the host project directory was requested.
    if print_path:
        # If the observation does not report the project bind.
        if box.workspace is None:
            # Throw the current CLI-local error.
            raise SandboxError(f"Box `{project}` has no project directory bind mount.")

        # Read the host project directory.
        project_dir: Path = box.workspace.host_directory

        # If the host project directory no longer exists.
        if not project_dir.is_dir():
            # Throw the current CLI-local error.
            raise SandboxError(f"Project directory `{project_dir}` for box `{project}` no longer exists.")

        # Print the raw path and newline for command substitution.
        click.echo(str(project_dir))

        # Stop after the path.
        return

    # Read the display facts with explicit fallbacks for unavailable fields.
    container_id: str = sanitize_value(box.backend.id if box.backend is not None else "unknown")


# Render one mount category with its compatibility markers.
def _render_mounts(mounts: tuple[Mount, ...], *, mounts_available: bool) -> None:
    # If mounts are attached.
    if mounts:
        # Display each sanitized source and target.
        for mount in mounts:
            # Render one mount arrow.
            click.echo(f"  {sanitize_value(mount.source)} -> {sanitize_value(mount.target)}")

    # If the runtime reports no mounts.
    elif not mounts_available:
        # Display the unavailable marker.
        click.echo("  ?")

    # Otherwise.
    else:
        # Display the empty marker.
        click.echo("  None")


# Render one network attachment.
def _render_network(network: Network) -> None:
    # Read the sanitized name.
    name: str = sanitize_value(network.name)

    # If the network has an assigned address.
    if network.ip_address:
        # Display the name and address.
        click.echo(f"  {name} -> {sanitize_value(network.ip_address)}")
    else:
        # Display the name alone.
        click.echo(f"  {name}")
