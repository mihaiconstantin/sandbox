"""Verify public client construction, home scoping, and inert import boundaries."""

# Imports.
import subprocess
import sys
from pathlib import Path

import pytest

# Import the SDK client and operation objects.
from sandbox.sdk import BoxOperations, CatalogueOperations, SandboxClient, SecretOperations, VolumeOperations

# Import the shipped fakes.
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime


# Verify construction requires keyword-only explicit collaborators.
def test_construction_is_keyword_only(tmp_path: Path) -> None:
    # Reject positional construction.
    with pytest.raises(TypeError):
        SandboxClient(tmp_path, FakeRuntime(), FakeBuilder())  # pyright: ignore[reportCallIssue]


# Verify the client exposes its home and four eagerly constructed operation objects.
def test_client_exposes_home_and_operations(tmp_path: Path) -> None:
    # Construct the client over a nonexistent home.
    client = SandboxClient(home = tmp_path / "missing", runtime = FakeRuntime(), builder = FakeBuilder())

    # Require the supplied home and the four operation objects.
    assert client.home == tmp_path / "missing"
    assert isinstance(client.boxes, BoxOperations)
    assert isinstance(client.volumes, VolumeOperations)
    assert isinstance(client.catalogues, CatalogueOperations)
    assert isinstance(client.secrets, SecretOperations)


# Verify construction performs no path resolution or home read.
def test_construction_is_filesystem_inert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail if construction resolves or expands the home.
    def refuse_expand(self: Path) -> Path:
        raise AssertionError("construction must not expand paths")

    def refuse_resolve(self: Path, strict: bool = False) -> Path:
        raise AssertionError("construction must not resolve paths")

    monkeypatch.setattr(Path, "expanduser", refuse_expand)
    monkeypatch.setattr(Path, "resolve", refuse_resolve)

    # Construct the client over a missing home.
    home = tmp_path / "missing"
    client = SandboxClient(home = home, runtime = FakeRuntime(), builder = FakeBuilder())

    # Require the exact home and no created directory.
    assert client.home is home
    assert not home.exists()


# Verify the silent default writes nothing and home scoping stays independent.
def test_clients_are_home_scoped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Construct two independent clients.
    first = SandboxClient(home = tmp_path / "one", runtime = FakeRuntime(), builder = FakeBuilder())
    second = SandboxClient(home = tmp_path / "two", runtime = FakeRuntime(), builder = FakeBuilder())

    # Read through the public operations without output.
    assert first.boxes.get("missing") is None
    assert second.volumes.list() == ()

    # Require distinct homes and no captured output.
    assert first.home != second.home
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# Verify importing the SDK package pulls no presentation or backend modules.
def test_sdk_import_is_presentation_and_backend_free() -> None:
    # Declare the blocked module roots.
    script = """
import importlib.abc
import sys

BLOCKED = (
    "click",
    "rich",
    "docker",
    "compose",
    "sandbox.cli",
    "sandbox.composition",
    "sandbox.integrations",
)

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(f"{name}.") for name in BLOCKED):
            raise ImportError(f"blocked import: {fullname}")
        return None

sys.meta_path.insert(0, Blocker())
import sandbox.sdk
from sandbox.sdk import SandboxClient, CreateBoxRequest
print("ok")
"""

    # Run the import in a fresh interpreter.
    completed = subprocess.run([sys.executable, "-c", script], capture_output = True, text = True)

    # Require a clean import.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
