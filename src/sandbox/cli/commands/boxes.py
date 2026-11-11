# Imports.
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import click

# Import the CLI helpers.
from sandbox.cli.completion import complete_projects
from sandbox.cli.context import client_for, cli_context, default_home
from sandbox.cli.parameters import catalogue_argument, home_option, project_argument

# Import the public box values.
from sandbox.domain import RemovalPlan, RuntimeRef, secret_target

# Import the typed missing-secret failures.
from sandbox.errors.secrets import MissingSecret, SecretError

# Import the public SDK request.
from sandbox.sdk import CreateBoxRequest, CreateBoxResult, SandboxClient


# Check whether the command has an interactive terminal.
def is_interactive() -> bool:
    # Return whether standard input is a terminal.
    return sys.stdin.isatty()


# Prompt for a readable secret file.
def prompt_secret_file() -> Path:
    # Repeat until a valid file is provided.
    while True:
        # Ask for the secret file path.
        value: str = click.prompt("Path to secret file", type = str)

        # Expand the user directory.
        path: Path = Path(value).expanduser()

        # If the file is not readable.
        if not path.is_file() or not os.access(path, os.R_OK):
            # User feedback.
            click.secho(f"Secret file `{path}` does not exist or is not readable.", fg = "red")

            # Ask again.
            continue

        # Return the resolved file path without reading its contents.
        return path.resolve()


# Compose the actionable command that binds a missing secret.
def secret_command_hint(error: MissingSecret, home: Path) -> str:
    # Resolve the selected home so the hint matches the binding location.
    selected_home: Path = home.expanduser().resolve()

    # Compose the command that binds the missing secret in its catalogue.
    command_hint: str = f"sb create secret {error.alias} --file <path> --catalogue {error.catalogue}"

    # If the selected home differs from the default home.
    if selected_home != default_home().expanduser().resolve():
        # Append the selected home so the binding is saved where this command reads it.
        command_hint += f" --home {selected_home}"

    # Return the complete hint.
    return command_hint
