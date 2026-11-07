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
