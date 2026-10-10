# Imports.
from __future__ import annotations

from dataclasses import dataclass

# Import the output port values.
from sandbox.ports.output import OutputChannel, ProgressPhase


# Represent one recorded progress event.
@dataclass(frozen = True, slots = True)
class RecordedProgress:
    # Record the reported phase.
    phase: ProgressPhase

    # Record the optional untrusted display subject.
    subject: str | None
