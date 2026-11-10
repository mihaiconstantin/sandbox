# Imports.
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast

import click

# Import the neutral validation rules.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.identifiers import validate_identifier, validate_volume_name

# Describe one Click decorator that preserves the decorated function type.
CommandFunction = TypeVar("CommandFunction", bound = Callable[..., object])


# Build the `sandbox` home option decorator shared by resource commands.
def home_option(*, exists: bool = False) -> Callable[[CommandFunction], CommandFunction]:
    # Apply the current home default and help text.
    return cast(
        Callable[[CommandFunction], CommandFunction],
        click.option(
            "-h", "--home",
            type = click.Path(exists = exists, file_okay = False, dir_okay = True, path_type = Path),
            default = lambda: Path.home() / ".sandbox",
            show_default = "~/.sandbox",
            help = "The `sandbox` home directory containing catalogues and configuration.",
        ),
    )


# Convert one neutral identifier failure into a Click usage error.
def _identifier(ctx: click.Context, parameter: click.Parameter, value: str, field: str) -> str:
    # Validate through the shared rule.
    try:
        # Apply the lowercase namespace rule.
        validate_identifier(value, field)

    # Convert an invalid identifier into a Click parameter error.
    except ConfigurationError as error:
        # Throw with the usage exit class.
        raise click.BadParameter(error.message) from None

    # Return the validated value.
    return value


# Validate one project name supplied on the command line.
def project_argument(ctx: click.Context, parameter: click.Parameter, value: str) -> str:
    # Apply the project identifier rule.
    return _identifier(ctx, parameter, value, "project")


# Validate one catalogue name supplied on the command line.
def catalogue_argument(ctx: click.Context, parameter: click.Parameter, value: str) -> str:
    # Apply the catalogue identifier rule.
    return _identifier(ctx, parameter, value, "catalogue")


# Validate one secret alias supplied on the command line.
def secret_argument(ctx: click.Context, parameter: click.Parameter, value: str) -> str:
    # Apply the secret identifier rule.
    return _identifier(ctx, parameter, value, "secret")


# Validate one physical volume name supplied on the command line.
def volume_argument(ctx: click.Context, parameter: click.Parameter, value: str) -> str:
    # Validate through the shared physical-name rule.
    try:
        # Apply the Docker-compatible volume rule.
        validate_volume_name(value)

    # Convert an invalid name into a Click parameter error.
    except ConfigurationError as error:
        # Throw with the usage exit class.
        raise click.BadParameter(error.message) from None

    # Return the validated value.
    return value


# Define the public API of the `sandbox.cli.parameters` module.
__all__: list[str] = ["catalogue_argument", "home_option", "project_argument", "secret_argument", "volume_argument"]
