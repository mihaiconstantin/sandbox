# Imports.
from __future__ import annotations

import codecs

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

# Import the output port values.
from sandbox.ports.output import OutputChannel, OutputSink, ProgressPhase

# Import the display sanitizer.
from sandbox.cli.presentation.text import sanitize_process_output, sanitize_value


# Render the transient TTY-only wording for one progress phase.
def phase_text(phase: ProgressPhase, subject: str | None) -> str:
    # Sanitize the untrusted subject before display.
    safe_subject: str | None = None if subject is None else sanitize_value(subject)

    # Render the phase-specific wording.
    match phase:
        case ProgressPhase.PREPARE_IMAGE:
            return f"Preparing image {safe_subject or ''}".rstrip()
        case ProgressPhase.BUILD_IMAGE:
            return f"Building image {safe_subject or ''}".rstrip()
        case ProgressPhase.ENSURE_VOLUME:
            return f"Ensuring volume `{safe_subject or ''}`".rstrip()
        case ProgressPhase.CREATE:
            return f"Creating box `{safe_subject or ''}`".rstrip()
        case ProgressPhase.START:
            return f"Starting box `{safe_subject or ''}`".rstrip()
        case ProgressPhase.STOP:
            return f"Stopping box `{safe_subject or ''}`".rstrip()
        case ProgressPhase.REMOVE:
            return f"Removing box `{safe_subject or ''}`".rstrip()
        case ProgressPhase.REMOVE_VOLUME:
            return f"Removing volume `{safe_subject or ''}`".rstrip()
        case _:
            return "Working"


# Translate SDK output into transient status and raw child output on stderr.
class CliOutput(OutputSink):
    # Bind the sink to the per-invocation stderr console and TTY policy.
    def __init__(self, console: Console, *, is_terminal: bool | None = None) -> None:
        # Store the console and whether transient status is allowed.
        self._console: Console = console
        self._is_terminal: bool = bool(console.is_terminal) if is_terminal is None else is_terminal

        # Create one incremental UTF-8 decoder per child channel.
        self._decoders: dict[OutputChannel, codecs.IncrementalDecoder] = {
            OutputChannel.STDOUT: codecs.getincrementaldecoder("utf-8")(errors = "replace"),
            OutputChannel.STDERR: codecs.getincrementaldecoder("utf-8")(errors = "replace"),
        }

        # Track the active status and whether the invocation has finished.
        self._status: Live | None = None
        self._plain_status: bool = False
        self._closed: bool = False

    # Scope transient status and child decoding to one command operation.
    def __enter__(self) -> CliOutput:
        # Return the sink for direct use inside the scope.
        return self

    # Report one advisory progress phase as transient stderr status.
    def progress(self, phase: ProgressPhase, *, subject: str | None = None) -> None:
        # Suppress status when the stream is not an interactive terminal.
        if not self._is_terminal or self._closed:
            # The silent pipe path is deterministic.
            return

        # Render the phase text.
        text: str = phase_text(phase, subject)

        # Fall back to a plain status line for a dumb console that was explicitly injected.
        if self._console.is_dumb_terminal:
            # Replace the transient line without Rich live rendering.
            self._console.file.write(f"{text}\r")
            self._console.file.flush()
            self._plain_status = True
            return

        # Start or update the single status line.
