# Imports.
from __future__ import annotations

from dataclasses import dataclass


# Represent an expected failure that crosses the public boundary.
class SandboxError(Exception):
    # No additional behavior.
    pass
