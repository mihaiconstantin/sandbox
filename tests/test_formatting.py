# Imports.
import unittest

import click
from click.testing import CliRunner, Result

# Import formatting.
from sandbox.cli.presentation.table import render_table


# Verify shared table rendering aligns and pads columns.
class RenderTableTests(unittest.TestCase):
    # Verify a column widens to fit a value longer than its header.
    def test_renders_aligned_columns(self) -> None:
        # Define a command that renders one table.
        @click.command()
        def command() -> None:
            render_table(("NAME", "STATUS"), [("short", "running"), ("a-longer-name", "up")])

        # Invoke the command to capture the rendered table.
        result: Result = CliRunner().invoke(command, [])

        # Require the exact header, separator, and padded cells.
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            result.output,
            (
                "NAME           STATUS \n"
                "short          running\n"
                "a-longer-name  up     \n"
            ),
        )

    # Verify a column keeps the header width when the header is widest.
    def test_uses_header_width_when_the_header_is_widest(self) -> None:
        # Define a command that renders headers wider than every value.
        @click.command()
        def command() -> None:
            render_table(("REFERENCE", "FILE"), [("a", "b"), ("xy", "z")])

        # Invoke the command to capture the rendered table.
        result: Result = CliRunner().invoke(command, [])

        # Require header-driven widths with padded rows and trailing spaces.
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            result.output,
            (
                "REFERENCE  FILE\n"
                "a          b   \n"
                "xy         z   \n"
            ),
        )


# Allow the focused tests to run without a third-party test framework.
if __name__ == "__main__":
    unittest.main()
