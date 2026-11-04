# Imports.
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

# Import the transient output sink.
from sandbox.cli.presentation.output import CliOutput

# Import the default runtime vocabulary.
from sandbox.cli.presentation.vocabulary import DOCKER_VOCABULARY, RuntimeVocabulary


# Report whether a text stream is an interactive terminal.
def stream_is_terminal(stream: object) -> bool:
    # Read the stream's own probe when one exists.
    probe: Any = getattr(stream, "isatty", None)

    # If the probe is callable.
    if callable(probe):
        # Prefer the stream's own terminal fact.
        try:
            # Return the reported terminal fact.
            return bool(probe())

        # Treat an unavailable probe as a pipe.
        except (OSError, ValueError):
            # The stream is not an interactive terminal.
            return False

    # Treat a missing probe as a pipe.
    return False


# Report whether the selected terminal is declared dumb or unknown.
def term_is_dumb() -> bool:
    # Read the terminal type.
    return os.environ.get("TERM", "").strip().lower() in ("dumb", "unknown")


# Report whether the environment disables color explicitly.
def no_color_requested() -> bool:
    # Treat any non-empty `NO_COLOR` as a color veto.
    return bool(os.environ.get("NO_COLOR"))


# Construct the one stderr Rich console for one invocation.
def stderr_console() -> Console:
    # Read the interactive and dumb terminal facts.
    is_terminal: bool = stream_is_terminal(sys.stderr)
    is_dumb: bool = term_is_dumb()

    # Construct the stderr console without pinning `file=`.
    kwargs: dict[str, Any] = {
        "stderr": True,
        "markup": False,
        "emoji": False,
        "highlight": False,
    }

    # Use deterministic settings on a pipe or dumb terminal.
    if not is_terminal or is_dumb:
        # Disable animation, color, and host-dependent width.
        kwargs.update(force_terminal = False, color_system = None, width = 80)

    # Honor `NO_COLOR` on any stream.
    if no_color_requested():
        # Disable color output.
        kwargs["no_color"] = True

    # Build the one console for this invocation.
    return Console(**kwargs)
