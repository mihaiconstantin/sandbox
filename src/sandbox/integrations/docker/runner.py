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
