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
