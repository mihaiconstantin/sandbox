# Imports.
from __future__ import annotations

from dataclasses import dataclass


# Represent an expected failure that crosses the public boundary.
class SandboxError(Exception):
    # No additional behavior.
    pass


# Represent invalid caller input with the documented builtin compatibility base.
class InputError(SandboxError, ValueError):
    # No additional behavior.
    pass
