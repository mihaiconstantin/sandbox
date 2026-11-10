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


# Own the one stderr Rich console constructed for one CLI invocation.
@dataclass
class CliPresentation:
    # Hold the single stderr console.
    err: Console

    # Report whether stderr is an interactive terminal.
    is_terminal: bool = False

    # Report whether the terminal is dumb or unknown.
    is_dumb_terminal: bool = False

    # Hold the composition-supplied runtime vocabulary.
    vocabulary: RuntimeVocabulary = DOCKER_VOCABULARY

    # Expose the SDK output sink bound to this console.
    output: CliOutput = field(init = False)

    # Build the output sink after the console policy is known.
    def __post_init__(self) -> None:
        # Allow transient status only on a real, non-dumb terminal.
        self.output = CliOutput(self.err, is_terminal = self.is_terminal and not self.is_dumb_terminal)

    # Construct the production presentation with pipe-safe console settings.
    @classmethod
    def attach(
        cls,
        *,
        vocabulary: RuntimeVocabulary | None = None,
        console: Console | None = None,
    ) -> CliPresentation:
        # Honor an explicitly injected console without changing its policy.
        if console is not None:
            # Read the injected console's own terminal facts.
            return cls(
                err = console,
                is_terminal = bool(console.is_terminal),
                is_dumb_terminal = bool(console.is_dumb_terminal),
                vocabulary = vocabulary or DOCKER_VOCABULARY,
            )

        # Read the interactive and dumb terminal facts.
        is_terminal: bool = stream_is_terminal(sys.stderr)
        is_dumb: bool = term_is_dumb()

        # Build the one stderr console for this invocation.
        return cls(
            err = stderr_console(),
            is_terminal = is_terminal,
            is_dumb_terminal = is_dumb,
            vocabulary = vocabulary or DOCKER_VOCABULARY,
        )

    # Stop transient status before the invocation completes.
    def close(self) -> None:
        # Finalize the output sink.
        self.output.close()


# Define the public API of the `sandbox.cli.presentation.console` module.
__all__: list[str] = ["CliPresentation", "no_color_requested", "stderr_console", "stream_is_terminal", "term_is_dumb"]
