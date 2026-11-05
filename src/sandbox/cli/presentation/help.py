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
