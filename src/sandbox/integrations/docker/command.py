# Imports.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Import the neutral output contract and its silent default.
from sandbox.ports.output import SILENT, OutputSink

# Bound every diagnostic line that can cross the public boundary.
DIAGNOSTIC_LIMIT: int = 4096
