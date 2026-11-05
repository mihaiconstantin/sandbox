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

    # Write a definition list, coloring command names in the commands section.
    def write_dl(self: StyledHelpFormatter, rows: list[tuple[str, str]], *args: Any, **kwargs: Any) -> None:
        # If the current section lists commands.
        if self._section == "Commands":
            # Color the command names in the definition list.
            rows = [(click.style(name, fg = "green", bold = True), text) for name, text in rows]

        # Then, write the definition list.
        super().write_dl(rows, *args, **kwargs)


# Define the Click context with deterministic pipe width and color.
class SandboxContext(click.Context):
    # Use the compatibility help formatter.
    formatter_class = StyledHelpFormatter

    # Configure help width and color from the stream and environment.
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Initialize the base context.
        super().__init__(*args, **kwargs)

        # Read whether standard output is a terminal.
        is_terminal: bool = stream_is_terminal(sys.stdout)

        # Pin the compatibility help width under a pipe.
        if not is_terminal:
            # Ignore `COLUMNS` and terminal probes.
            self.terminal_width = 80

        # Disable color on a pipe, a dumb terminal, or explicit `NO_COLOR`.
        if not is_terminal or term_is_dumb() or no_color_requested():
            # Pin plain output.
            self.color = False


# Apply the styled help context to a command and its subcommands.
def apply_styled_context(command: click.Command) -> None:
    # Use the styled context for this command.
    command.context_class = SandboxContext

    # If the command is a group.
    if isinstance(command, click.Group):
        # Declare the subcommand.
        subcommand: click.Command

        # Recurse into each subcommand.
        for subcommand in command.commands.values():
            # Apply the same context recursively.
            apply_styled_context(subcommand)


# Configure the styled help text and epilog for the root command.
def configure_help(command: click.Command) -> None:
    # Set the styled help text.
    command.help = inspect.cleandoc(
        f"""
            {click.style("`sandbox`", fg = "blue", bold = True)} or {click.style("`sb`", fg = "blue", bold = True)} is a tool for managing isolated development environments.
        """
    )

    # Set the extended help pointer to appear after the command list.
    command.epilog = inspect.cleandoc(
        f"""
        Run `{click.style("sb", fg = "blue", bold = True)} {click.style("guide", fg = "green", bold = True)}` for getting started.
        """
    )
