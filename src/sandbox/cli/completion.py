# Imports.
from __future__ import annotations

from collections.abc import Callable

import click

# Import domain observations.
from sandbox.domain import BoxObservation, BoxState

# Import the CLI context helpers.
from sandbox.cli.context import client_for

# Import public errors.
from sandbox.errors import SandboxError


# List managed projects matching one predicate and the typed prefix.
def _complete_projects(ctx: click.Context, incomplete: str, predicate: Callable[[BoxObservation], bool]) -> list[str]:
    # Query the SDK and tolerate runtime or configuration failures.
    try:
        # Build the default client and list its boxes.
        boxes: tuple[BoxObservation, ...] = client_for(ctx).boxes.list()

    # Treat any public failure as no completion.
    except (SandboxError, OSError):
        # Return no suggestions.
        return []

    # Keep the projects whose boxes match the predicate and typed prefix.
    return [box.name for box in boxes if predicate(box) and box.name.startswith(incomplete)]
