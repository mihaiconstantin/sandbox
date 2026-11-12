"""Verify the composition initializer stays inert and exposes no transitional names."""

# Imports.
from __future__ import annotations

import os
import subprocess
import sys

# Locate the source tree from the test file.
SOURCE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


# Verify importing the package loads no composition submodule or retired surface.
def test_initializer_imports_no_composition_submodule() -> None:
    # Import the package in a fresh interpreter and inspect its surface.
    script: str = """
import sys
import sandbox.composition

# Require no eager import of any composition submodule.
loaded = sorted(
    name
    for name in sys.modules
    if name.startswith("sandbox.composition.") and name != "sandbox.composition"
)
assert loaded == [], loaded

# Require the retired application surface to stay absent.
for retired in ("SandboxApplicationFactory", "legacy", "main", "client"):
    assert not hasattr(sandbox.composition, retired), retired
assert sandbox.composition.__all__ == []
print("ok")
"""

    # Run the import against the source tree with no adapters in play.
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", script],
        capture_output = True,
        text = True,
        env = {**os.environ, "PYTHONPATH": SOURCE_ROOT},
    )

    # Require the clean surface.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
