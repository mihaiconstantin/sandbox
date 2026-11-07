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


# Report whether a box is running for completion filtering.
def _is_running(box: BoxObservation) -> bool:
    # Prefer the adapter display status when it is reported.
    if box.status_text is not None:
        # Match the running label.
        return box.status_text == "running"

    # Fall back to the neutral observed state.
    return box.state is BoxState.RUNNING


# Report whether a box has exited for completion filtering.
def _has_exited(box: BoxObservation) -> bool:
    # Prefer the adapter display status when it is reported.
    if box.status_text is not None:
        # Match the exited label.
        return box.status_text == "exited"

    # Fall back to the neutral stopped state.
    return box.state is BoxState.STOPPED


# Complete the projects of running boxes.
def complete_running_projects(ctx: click.Context, _parameter: click.Parameter, incomplete: str) -> list[str]:
    # Complete running projects.
    return _complete_projects(ctx, incomplete, _is_running)
