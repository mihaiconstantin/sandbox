"""Verify recorded progress phases and opaque child-process chunks."""

# Imports.
import pytest

# Import the output values and the recording fake.
from sandbox.ports import OutputChannel, ProgressPhase
from sandbox.testing.output import RecordedOutput, RecordedProgress, RecordingOutputSink


# Verify progress records the phase order and optional untrusted subject.
def test_recording_sink_records_progress_in_order() -> None:
    # Record two phases with and without a subject.
    sink: RecordingOutputSink = RecordingOutputSink()
    sink.progress(ProgressPhase.PREPARE_IMAGE)
    sink.progress(ProgressPhase.ENSURE_VOLUME, subject = "cache")

    # Compare the recorded progress.
    assert sink.progress_events == (
        RecordedProgress(phase = ProgressPhase.PREPARE_IMAGE, subject = None),
        RecordedProgress(phase = ProgressPhase.ENSURE_VOLUME, subject = "cache"),
    )
    assert sink.progress_phases == (ProgressPhase.PREPARE_IMAGE, ProgressPhase.ENSURE_VOLUME)
    assert sink.progress_subjects == (None, "cache")


# Verify process output preserves the channel and exact bytes, including splits.
def test_recording_sink_preserves_channel_and_split_bytes() -> None:
    # Record a split UTF-8 code point and an empty chunk.
    sink: RecordingOutputSink = RecordingOutputSink()
    sink.process_output(OutputChannel.STDOUT, b"\xe2")
    sink.process_output(OutputChannel.STDOUT, b"\x82\xac")
    sink.process_output(OutputChannel.STDERR, b"warning\n")
    sink.process_output(OutputChannel.STDERR, b"")

    # Compare the ordered chunks.
    assert sink.output_events == (
        RecordedOutput(channel = OutputChannel.STDOUT, data = b"\xe2"),
        RecordedOutput(channel = OutputChannel.STDOUT, data = b"\x82\xac"),
        RecordedOutput(channel = OutputChannel.STDERR, data = b"warning\n"),
        RecordedOutput(channel = OutputChannel.STDERR, data = b""),
    )

    # Compare the per-channel byte streams.
    assert sink.output_bytes(OutputChannel.STDOUT) == b"\xe2\x82\xac"
    assert sink.output_bytes(OutputChannel.STDERR) == b"warning\n"


# Verify the recorder rejects values outside the closed vocabulary.
def test_recording_sink_rejects_invalid_values() -> None:
    # Require typed phases, channels, and bytes.
    sink: RecordingOutputSink = RecordingOutputSink()
    with pytest.raises(ValueError):
        sink.progress("create")  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError):
        sink.process_output("stdout", b"data")  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError):
        sink.process_output(OutputChannel.STDOUT, "text")  # pyright: ignore[reportArgumentType]


# Verify a failed recording leaves prior events intact.
def test_recording_sink_keeps_prior_events_after_a_rejected_call() -> None:
    # Record one valid event and one invalid event.
    sink: RecordingOutputSink = RecordingOutputSink()
    sink.progress(ProgressPhase.CREATE)
    with pytest.raises(ValueError):
        sink.progress("start")  # pyright: ignore[reportArgumentType]

    # Require the prior event to remain.
    assert sink.progress_phases == (ProgressPhase.CREATE,)


# Allow the focused tests to run directly.
if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
