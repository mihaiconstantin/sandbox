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
