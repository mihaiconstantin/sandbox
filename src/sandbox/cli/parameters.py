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
