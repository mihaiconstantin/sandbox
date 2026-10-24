"""Verify the Docker subprocess runner at its process seam."""

# Imports.
import os
import sys
import threading
from pathlib import Path

# Import pytest for assertions on raised interruptions.
import pytest

# Import the integration runner and output channels.
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.runner import SubprocessRunner
from sandbox.ports.output import OutputChannel
from sandbox.testing.output import RecordingOutputSink


# Verify captured output preserves binary bytes, statuses, and bounded diagnostics.
def test_captured_output_preserves_binary_bytes_and_status() -> None:
    # Run a child that writes binary output on both streams and exits non-zero.
    result: CommandResult = SubprocessRunner().run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'out\\xff'); sys.stderr.buffer.write(b'first\\nlast line\\n'); sys.exit(7)",
        ]
    )

    # Require the raw status and complete binary captures.
    assert result.returncode == 7
    assert result.stdout == b"out\xff"
    assert result.stderr == b"first\nlast line\n"

    # Require the bounded, decoded last diagnostic line.
    assert result.diagnostic == "last line"


# Verify streamed chunks keep their channel and a bounded diagnostic tail.
def test_streaming_output_preserves_channels_and_tail() -> None:
    # Record the streamed chunks.
    sink: RecordingOutputSink = RecordingOutputSink()

    # Run a child that writes distinct payloads on each stream.
    result: CommandResult = SubprocessRunner().run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'stdout payload'); sys.stderr.buffer.write(b'stderr payload\\n'); sys.exit(3)",
        ],
        capture = False,
        output = sink,
    )

    # Require the child status and exact channel routing.
    assert result.returncode == 3
    assert sink.output_bytes(OutputChannel.STDOUT) == b"stdout payload"
    assert sink.output_bytes(OutputChannel.STDERR) == b"stderr payload\n"

    # Require the tail to keep the last diagnostic line without the full capture.
    assert result.diagnostic == "stderr payload"
    assert result.stdout == b"stdout payload"


# Verify dual large pipes cannot deadlock through the bounded queue.
def test_large_dual_pipe_output_does_not_deadlock() -> None:
    # Prepare a result holder and one worker thread.
    outcome: list[CommandResult] = []
    errors: list[BaseException] = []

    # Run the child on a worker so a deadlock can be detected by the test.
    def execute() -> None:
        # Run a child that writes more than a pipe buffer on both streams.
        try:
            # Record the completed command.
            outcome.append(
                SubprocessRunner().run(
                    [
                        sys.executable,
                        "-c",
                        "import sys; sys.stdout.buffer.write(b'o' * 262144); sys.stderr.buffer.write(b'e' * 262144)",
                    ]
                )
            )

        # Record an unexpected failure.
        except BaseException as error:
            # Preserve the failure for the assertion.
            errors.append(error)

    # Start the worker.
    worker: threading.Thread = threading.Thread(target = execute, daemon = True)
    worker.start()

    # Require the child to finish instead of blocking on either pipe.
    worker.join(timeout = 10.0)
    assert not worker.is_alive()
    assert errors == []
    assert len(outcome) == 1
    assert len(outcome[0].stdout) == 262144
    assert len(outcome[0].stderr) == 262144


# Verify an interrupted command terminates its process group and is reaped.
def test_interruption_terminates_the_process_group() -> None:
    # Record the child identifier printed before the interruption.
    identifiers: list[int] = []

    # Interrupt the caller thread after the child announces that it is running.
    class _InterruptingSink:
        # Record progress without an effect.
        def progress(self, phase: object, *, subject: str | None = None) -> None:
            # Do nothing; the runner test only cares about process output.
            return None

        # Interrupt on the first child chunk.
        def process_output(self, channel: OutputChannel, data: bytes) -> None:
            # Record the announced process identifier.
            identifiers.append(int(data.decode("ascii").strip()))

            # Simulate a terminal interrupt.
            raise KeyboardInterrupt

    # Require the interruption to propagate unchanged.
    with pytest.raises(KeyboardInterrupt):
        # Run a process that announces its identifier and then waits.
        SubprocessRunner().run(
            [
                sys.executable,
                "-c",
                "import os, sys, time; print(os.getpid(), flush=True); time.sleep(60)",
            ],
            capture = False,
            output = _InterruptingSink(),
        )

    # Require the child to be gone after the runner returned the interruption.
    assert len(identifiers) == 1
    with pytest.raises(ProcessLookupError):
        # Probe the terminated child without sending a signal.
        os.kill(identifiers[0], 0)


# Verify inherited-stdio commands preserve the raw status.
def test_interactive_command_preserves_status(tmp_path: Path) -> None:
    # Run one short child with inherited streams.
    result: CommandResult = SubprocessRunner().run_interactive([sys.executable, "-c", "raise SystemExit(9)"])

    # Require the raw status and no captured bytes.
    assert result.returncode == 9
    assert result.stdout == b""
    assert result.stderr == b""
