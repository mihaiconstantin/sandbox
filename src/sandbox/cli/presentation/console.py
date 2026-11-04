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
