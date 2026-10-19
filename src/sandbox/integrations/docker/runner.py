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
