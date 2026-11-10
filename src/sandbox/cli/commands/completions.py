# Imports.
from __future__ import annotations

import click
from click.shell_completion import shell_complete


# Print one supported shell completion script without constructing a client.
@click.command(name = "completions")
@click.argument(
    "shell",
    type = click.Choice(["bash", "zsh", "powershell"]),
)
@click.pass_context
def completions(context: click.Context, shell: str) -> None:
    """Print a shell completion script.

    `SHELL` is one of `bash`, `zsh`, or `powershell`.
    """

    # Resolve the root command and executable name.
    root: click.Context = context.find_root()
    name: str = root.command_path

    # Match Click's completion environment-variable convention.
    complete_var: str = f"_{name.replace('-', '_').replace('.', '_')}_COMPLETE".upper()

    # Print Click's generated completion script.
    status: int = shell_complete(root.command, {}, name, complete_var, f"{shell}_source")

    # If the installed Click does not support this shell.
    if status != 0:
        # Explain the missing shell implementation.
        raise click.ClickException(f"The installed Click version does not support {shell} completion.")


# Define the public API of the `sandbox.cli.commands.completions` module.
__all__: list[str] = ["completions"]
