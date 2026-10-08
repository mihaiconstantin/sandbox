# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank

# Import the observed runtime reference.
from sandbox.domain.observation import RuntimeRef
