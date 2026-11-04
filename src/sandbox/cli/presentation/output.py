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

    # Finalize transient output when the operation scope ends.
    def __exit__(self, *_: object) -> None:
        # Stop status and flush child decoding.
        self.close()

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
        if self._status is None:
            # Create a transient live status with a neutral spinner.
            self._status = Live(
                Spinner("dots", text = text),
                console = self._console,
                transient = True,
                auto_refresh = True,
                refresh_per_second = 12.5,
            )

            # Render the first status immediately.
            self._status.start(refresh = True)
        else:
            # Update the existing status with a new phase.
            self._status.update(Spinner("dots", text = text), refresh = True)

    # Forward one opaque child chunk to stderr without markup parsing.
    def process_output(self, channel: OutputChannel, data: bytes) -> None:
        # Normalize the channel while accepting protocol-compatible string values.
        normalized: OutputChannel = channel if isinstance(channel, OutputChannel) else OutputChannel(channel)

        # Decode incrementally so split UTF-8 sequences survive.
        text: str = self._decoders[normalized].decode(data)

        # Ignore an incomplete chunk with no decodable text yet.
        if not text:
            # Return until the next chunk supplies the remaining bytes.
            return

        # Strip ANSI and unsafe controls on a pipe.
        if not self._is_terminal:
            # Keep line structure while removing terminal control sequences.
            text = sanitize_process_output(text)

        # Suspend the status before writing raw child output.
        self._stop_status()

        # Write and flush without Rich markup or wrapping.
        self._console.file.write(text)
        self._console.file.flush()

    # Stop the transient status before the invocation completes.
    def close(self) -> None:
        # Ignore repeated finalization.
        if self._closed:
            # Return without decoding the children twice.
            return

        # Mark the sink as closed.
        self._closed = True

        # Stop and discard the active status line.
        self._stop_status()

        # Flush any final decoder replacement characters.
        for decoder in self._decoders.values():
            # Decode the final bytes.
            text: str = decoder.decode(b"", final = True)

            # Write a final replacement character when needed.
            if text:
                # Sanitize pipe output.
                if not self._is_terminal:
                    # Strip terminal controls.
                    text = sanitize_process_output(text)

                # Write the final text plainly.
                self._console.file.write(text)

        # Flush whatever the decoders completed.
        self._console.file.flush()

    # Stop and drop the current status line before raw output.
    def _stop_status(self) -> None:
        # Clear the plain fallback status marker.
        if self._plain_status:
            # Flush the transient line before durable output.
            self._console.file.flush()
            self._plain_status = False

        # If a Rich status is active.
        if self._status is not None:
            # Stop it and clear it so the next phase can start a fresh line.
            self._status.stop()
            self._status = None


# Define the public API of the `sandbox.cli.presentation.output` module.
__all__: list[str] = ["CliOutput", "phase_text"]
