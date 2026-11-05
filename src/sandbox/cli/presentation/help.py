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

    # Track the section being written so definition lists can be styled selectively.
    @contextmanager
    def section(self: StyledHelpFormatter, name: str) -> Generator[None]:
        # Save the previous section before entering the new one.
        previous: str | None = self._section

        # Use the conventional heading for positional arguments.
        if name == "Positional arguments":
            # Rename the section.
            name = "Arguments"

        # Record the active section name.
        self._section = name

        # Track the base section context.
        try:
            # Enter the base formatter's section.
            with super().section(name):
                # Run the wrapped block.
                yield
        # Restore the previous section in all cases.
        finally:
            # Restore the previous section.
            self._section = previous

    # Write a section heading with the requested styling when applicable.
    def write_heading(self: StyledHelpFormatter, heading: str) -> None:
        # If the heading belongs to one of the generated help sections.
        if heading in ("Arguments", "Options", "Commands"):
            # Style the heading.
            heading = click.style(f"{heading}:", bold = True, underline = True)

            # Write the heading with the current indentation.
            self.write(f"{'':>{self.current_indent}}{heading}\n\n")

            # Return.
            return

        # Otherwise.
        super().write_heading(heading)
