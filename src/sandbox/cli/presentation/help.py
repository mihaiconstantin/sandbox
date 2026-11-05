# Imports.
from __future__ import annotations

import inspect
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import click

# Import the terminal environment helpers.
from sandbox.cli.presentation.console import no_color_requested, stream_is_terminal, term_is_dumb


# Format generated help sections with the compatibility styling.
class StyledHelpFormatter(click.HelpFormatter):
    # Initialize the formatter without an active section.
    def __init__(self: StyledHelpFormatter, *args: Any, **kwargs: Any) -> None:
        # Initialize the base formatter.
        super().__init__(*args, **kwargs)

        # Set the current section to `None`.
        self._section: str | None = None
