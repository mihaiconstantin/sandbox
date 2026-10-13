"""Verify the neutral ports package, closed output vocabulary, and silent default."""

# Imports.
import pytest

# Import the package and its final protocols.
import sandbox.ports
from sandbox.ports import Builder, OutputChannel, OutputSink, ProgressPhase, Runtime, RuntimePreparation, SILENT

# Import the port submodules.
from sandbox.ports import builder as builder_module
from sandbox.ports import runtime as runtime_module

# Import the shipped fakes.
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.output import RecordingOutputSink
from sandbox.testing.runtime import FakeRuntime


# Verify the package exports the final protocols from their dedicated modules.
def test_package_exports_the_final_protocols() -> None:
    # Require the final package names to resolve to the dedicated modules.
    assert Builder is builder_module.Builder
    assert Runtime is runtime_module.Runtime
    assert RuntimePreparation is runtime_module.RuntimePreparation
    assert sandbox.ports.OutputSink is OutputSink

    # Require the output values in the package initializer.
    assert sandbox.ports.ProgressPhase is ProgressPhase
    assert sandbox.ports.OutputChannel is OutputChannel
    assert sandbox.ports.SILENT is SILENT


# Verify the progress vocabulary is closed and complete.
def test_progress_phases_are_the_closed_neutral_vocabulary() -> None:
    # Compare the complete ordered vocabulary.
    assert tuple(phase.value for phase in ProgressPhase) == (
        "prepare-image",
        "build-image",
        "ensure-volume",
        "create",
        "start",
        "stop",
        "remove",
        "remove-volume",
    )

    # Require no initialization phase because no I/O occurs between planning and create.
    assert "initialize" not in {phase.value for phase in ProgressPhase}


# Verify child channels preserve the original stream identity.
def test_output_channels_are_stdout_and_stderr() -> None:
    # Compare the closed channel vocabulary.
    assert tuple(channel.value for channel in OutputChannel) == ("stdout", "stderr")


# Verify the silent default is stateless and accepts every operation.
def test_silent_is_a_stateless_noop_sink() -> None:
    # Require the silent default to satisfy the protocol.
    assert isinstance(SILENT, OutputSink)

    # Require every method to accept its arguments without writing or returning a value.
    assert SILENT.progress(ProgressPhase.CREATE) is None
    assert SILENT.progress(ProgressPhase.ENSURE_VOLUME, subject = "cache") is None
    assert SILENT.process_output(OutputChannel.STDOUT, b"partial") is None
    assert SILENT.process_output(OutputChannel.STDERR, b"") is None

    # Require a plain object not to satisfy the sink protocol.
    assert not isinstance(object(), OutputSink)


# Verify plain objects do not satisfy the protocols while shipped fakes do.
def test_protocols_accept_the_shipped_fakes() -> None:
    # Require the fakes to satisfy their ports structurally.
    assert isinstance(FakeBuilder(), Builder)
    assert isinstance(FakeRuntime(), Runtime)
    assert isinstance(RecordingOutputSink(), OutputSink)

    # Require plain objects to fail the runtime checks.
    assert not isinstance(object(), Builder)
    assert not isinstance(object(), Runtime)


# Verify neither port imports backend or presentation modules at import time.
def test_port_modules_import_without_backend_or_presentation_modules() -> None:
    # Require the neutral modules to be importable in a clean interpreter slice.
    import ast
    from pathlib import Path

    # Locate the port package.
    package = Path(sandbox.ports.__file__).parent

    # Collect every imported module name without importing it.
    imported: set[str] = set()
    for path in sorted(package.rglob("*.py")):
        tree: ast.Module = ast.parse(path.read_text(encoding = "utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

    # Require no adapter, presentation, or CLI module in the port package.
    forbidden: tuple[str, ...] = (
        "sandbox.cli",
        "sandbox.composition",
        "sandbox.configuration",
        "sandbox.catalogue",
        "sandbox.integrations",
        "docker",
        "compose",
        "click",
        "rich",
    )
    for module in imported:
        assert not any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden), module


# Allow the focused tests to run directly.
if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
