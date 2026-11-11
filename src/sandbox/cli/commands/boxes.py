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
