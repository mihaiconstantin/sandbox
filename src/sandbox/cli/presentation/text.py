# Imports.
from __future__ import annotations

import re

# Match ANSI CSI escape sequences.
_CSI: re.Pattern[str] = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# Match ANSI OSC escape sequences terminated by BEL or ST.
_OSC: re.Pattern[str] = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

# Match remaining two-character escape sequences.
_ESCAPE: re.Pattern[str] = re.compile(r"\x1b[@-_]")

# Match C0 and C1 control characters other than the permitted line controls.
_CONTROL: re.Pattern[str] = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
