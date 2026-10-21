# Imports.
from __future__ import annotations

import os
import signal
import subprocess
import threading
from collections.abc import Mapping, Sequence
from queue import Empty, Queue
from typing import BinaryIO

# Import the process seam and its result value.
from sandbox.integrations.docker.command import CommandResult
from sandbox.ports.output import SILENT, OutputChannel, OutputSink

# Bound the bytes retained for diagnostics on a streamed command.
DIAGNOSTIC_TAIL_LIMIT: int = 64 * 1024

# Bound the chunks waiting for the caller thread so readers apply back-pressure.
QUEUE_LIMIT: int = 64

# Read at most one page from a child pipe per operation.
READ_SIZE: int = 64 * 1024

# Allow a terminated child to exit before escalating the signal.
TERMINATION_TIMEOUT: float = 5.0


# Run child processes with binary pipes, process-group cleanup, and caller-thread delivery.
class SubprocessRunner:
    # Construct a runner with bounded diagnostic retention.
    def __init__(self, *, tail_limit: int = DIAGNOSTIC_TAIL_LIMIT) -> None:
        # Require a usable positive tail bound.
        if type(tail_limit) is not int or tail_limit <= 0:
            # Throw.
            raise ValueError("tail_limit must be a positive integer.")

        # Record the bounded diagnostic retention.
        self._tail_limit: int = tail_limit

    # Run one command with inherited standard streams and preserve its status.
    def run_interactive(
        self,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
    ) -> CommandResult:
        # Normalize the argument vector.
        command: tuple[str, ...] = tuple(arguments)

        # Require an actual command.
        if not command:
            # Throw.
            raise ValueError("arguments must contain at least one command argument.")

        # Inherit the caller's terminal so interactive shells keep their semantics.
        completed: subprocess.CompletedProcess[bytes] = subprocess.run(
            list(command),
            stdin = None,
            stdout = None,
            stderr = None,
            env = None if environment is None else dict(environment),
            check = False,
        )

        # Return the raw child status without interpreting it.
        return CommandResult(arguments = command, returncode = completed.returncode)

    # Read one binary pipe until end of stream.
    def _pump(self, stream: BinaryIO, channel: OutputChannel, queue: Queue[tuple[OutputChannel, bytes | None]]) -> None:
        # Read chunks until the child closes this pipe.
        try:
            # Loop over the page-sized reads.
            while True:
                # Read the next chunk from the binary stream.
                chunk: bytes = stream.read(READ_SIZE)

                # Stop at end of stream.
                if not chunk:
                    # Leave the loop.
                    break

                # Apply back-pressure through the bounded queue.
                self._put(queue, (channel, chunk))

        # Always signal end of stream to the caller thread.
        finally:
            # Report this pipe as finished.
            self._put(queue, (channel, None))

    # Put one queue item into the bounded queue.
    def _put(self, queue: Queue[tuple[OutputChannel, bytes | None]], item: tuple[OutputChannel, bytes | None]) -> None:
        # Block until the caller thread makes room, preserving the end-of-stream marker.
        queue.put(item)

    # Retain the final bytes of one stream up to the configured bound.
    def _append_tail(self, tail: bytearray, chunk: bytes) -> None:
        # Append the new chunk.
        tail.extend(chunk)

        # Drop the oldest bytes beyond the bound.
        if len(tail) > self._tail_limit:
            # Keep only the newest bounded suffix.
            del tail[: len(tail) - self._tail_limit]

    # Drain queued chunks after an interrupted command.
    def _drain(self, queue: Queue[tuple[OutputChannel, bytes | None]], streams: int) -> None:
        # Count the end-of-stream markers still expected.
        remaining: int = streams

        # Drain until every reader reports completion or the shutdown deadline expires.
        for _ in range(READ_SIZE):
            # Stop as soon as both readers are gone.
            if remaining <= 0:
                # Leave the drain loop.
                break

            # Check for one queued item without blocking forever.
            try:
                # Receive the next item.
                _, chunk = queue.get(timeout = 0.05)

            # Tolerate a reader that is still being stopped.
            except Empty:
                # Continue until the fixed attempt budget is exhausted.
                continue

            # Count a completed stream.
            if chunk is None:
                # Record the marker.
                remaining -= 1

    # Terminate the complete process group and reap the direct child.
    def _stop(self, process: subprocess.Popen[bytes]) -> None:
        # If the child already exited, only reap it.
        if process.poll() is not None:
            # Reap the direct child without another signal.
            process.wait()
            return

        # Ask the whole process group to terminate.
        try:
            # Signal every process in the child's group.
            os.killpg(process.pid, signal.SIGTERM)

        # Ignore a group that exited between the poll and the signal.
        except ProcessLookupError:
            # Continue to the status wait.
            pass

        # Wait for the group to exit.
