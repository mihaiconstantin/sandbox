# Imports.
from __future__ import annotations

from collections.abc import Sequence

import click

# Import the display sanitizer.
from sandbox.cli.presentation.text import sanitize_value


# Render the compatibility table with headers, order, and left alignment.
class TableRenderer:
    # Render one table to standard output.
    def render(self, headers: Sequence[str], rows: Sequence[Sequence[str]], *, color: bool | None = None) -> None:
        # Sanitize every header before width calculation.
        safe_headers: tuple[str, ...] = tuple(sanitize_value(header) for header in headers)

        # Sanitize every row value before width calculation.
        safe_rows: list[tuple[str, ...]] = [
            tuple(sanitize_value(value) for value in row)
            for row in rows
        ]

        # Compute the content-driven width of each column.
        widths: list[int] = [
            max([len(safe_headers[index]), *(len(row[index]) for row in safe_rows)])
            for index in range(len(safe_headers))
        ]

        # Display the bold header with the compatibility two-space separation.
        click.secho("  ".join(header.ljust(widths[index]) for index, header in enumerate(safe_headers)), bold = True, color = color)

        # Display each row with the same padding.
        for row in safe_rows:
            # Format the complete row, including incidental final-column padding.
            click.echo("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


# Render one table through the compatibility formatter.
def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, color: bool | None = None) -> None:
    # Delegate to the shared renderer.
    TableRenderer().render(headers, rows, color = color)


# Define the public API of the `sandbox.cli.presentation.table` module.
__all__: list[str] = ["TableRenderer", "render_table"]
