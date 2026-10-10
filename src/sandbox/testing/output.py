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


# Represent one recorded child-process chunk.
@dataclass(frozen = True, slots = True)
class RecordedOutput:
    # Record the original child channel.
    channel: OutputChannel

    # Record the exact opaque bytes.
    data: bytes


# Represent a test sink that records progress and child output in order.
class RecordingOutputSink:
    # Construct an empty recording sink.
    def __init__(self) -> None:
        # Create the ordered event logs.
        self._progress: list[RecordedProgress] = []
        self._output: list[RecordedOutput] = []

    # Read the recorded progress events.
    @property
    def progress_events(self) -> tuple[RecordedProgress, ...]:
        # Return an immutable snapshot.
        return tuple(self._progress)

    # Read the recorded child chunks.
    @property
    def output_events(self) -> tuple[RecordedOutput, ...]:
        # Return an immutable snapshot.
        return tuple(self._output)

    # Read the reported phases in order.
    @property
    def progress_phases(self) -> tuple[ProgressPhase, ...]:
        # Return the phase sequence.
        return tuple(event.phase for event in self._progress)

    # Read the reported subjects in order.
    @property
    def progress_subjects(self) -> tuple[str | None, ...]:
        # Return the subject sequence.
        return tuple(event.subject for event in self._progress)

    # Join the exact bytes recorded on one channel.
    def output_bytes(self, channel: OutputChannel) -> bytes:
        # Require a known channel.
        if not isinstance(channel, OutputChannel):
            # Throw.
            raise ValueError("channel must be an OutputChannel.")

        # Join the matching chunks in arrival order.
        return b"".join(event.data for event in self._output if event.channel is channel)

    # Record one progress phase.
    def progress(self, phase: ProgressPhase, *, subject: str | None = None) -> None:
        # Require the closed phase vocabulary.
        if not isinstance(phase, ProgressPhase):
            # Throw.
            raise ValueError("phase must be a ProgressPhase.")

        # Require a display subject when one is supplied.
        if subject is not None and not isinstance(subject, str):
            # Throw.
            raise ValueError("subject must be a string or `None`.")

        # Record the event.
        self._progress.append(RecordedProgress(phase = phase, subject = subject))
