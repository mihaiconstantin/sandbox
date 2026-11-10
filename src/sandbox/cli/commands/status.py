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
    container_name: str = sanitize_value(box.backend.name if box.backend is not None else "unknown")
    status_text: str = sanitize_value(box.status_text if box.status_text is not None else "unknown")
    image: str = sanitize_value(box.image if box.image is not None else "unknown")
    working_directory: str = sanitize_value(box.working_directory if box.working_directory is not None else "unknown")

    # Read the resource label from composition vocabulary.
    label: str = cli_context(ctx).vocabulary.label

    # Display the box identity and configuration fields.
    click.secho(f"Project          {sanitize_value(box.name)}", bold = True, color = ctx.color)
    click.echo(f"{label} ID      {container_id[:12]}")
    click.echo(f"{label} name    {container_name}")
    click.echo(f"Status            {status_text}")
    click.echo(f"Image             {image}")
    click.echo(f"Working directory {working_directory}")

    # Prepare the mount categories when the observation reports mounts.
    mounts: tuple[Mount, ...] | None = box.mounts
    secret_mounts: tuple[Mount, ...] = () if mounts is None else tuple(mount for mount in mounts if mount.target.startswith(f"{SECRET_ROOT}/"))
    other_mounts: tuple[Mount, ...] = () if mounts is None else tuple(mount for mount in mounts if not mount.target.startswith(f"{SECRET_ROOT}/"))
    volumes: tuple[Mount, ...] = tuple(mount for mount in other_mounts if mount.kind == "volume")
    project_binds: tuple[Mount, ...] = tuple(mount for mount in other_mounts if mount.kind == "bind")
    secrets: tuple[str, ...] = tuple(sorted(mount.target[len(SECRET_ROOT) + 1:] for mount in secret_mounts))

    # Display the named volumes.
    click.secho("\nVolumes", bold = True, color = ctx.color)
    _render_mounts(volumes, mounts_available = mounts is not None)

    # Display the host bind mounts.
    click.secho("\nBind mounts", bold = True, color = ctx.color)
    _render_mounts(project_binds, mounts_available = mounts is not None)

    # Display the attached secrets.
    click.secho("\nSecrets", bold = True, color = ctx.color)
    if secrets:
        # Display each secret and its container path.
        for secret in secrets:
            # Render one sanitized secret alias and guest path.
            click.echo(f"  {sanitize_value(secret)} -> {SECRET_ROOT}/{sanitize_value(secret)}")
    elif mounts is None:
        # Display the unavailable marker.
        click.echo("  ?")
    else:
        # Display the empty marker.
        click.echo("  None")

    # Display the attached networks.
    click.secho("\nNetworks", bold = True, color = ctx.color)
    if box.networks:
        # Display each network and its optional address.
        for network in box.networks:
            # Render the network through the shared sanitizer.
            _render_network(network)
    elif box.networks is None:
        # Display the unavailable marker.
        click.echo("  ?")
    else:
        # Display the empty marker.
        click.echo("  None")


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


# Define the public API of the `sandbox.cli.commands.status` module.
__all__: list[str] = ["status"]
