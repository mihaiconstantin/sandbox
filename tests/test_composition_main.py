"""Verify the production entry point injects presentation and stays inert before client use."""

# Imports.
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

# Import the composition entry point under test.
import sandbox.composition.main as composition_main

# Import the CLI context and presentation values.
from sandbox.cli.context import CliContext
from sandbox.composition.client import SandboxClientFactory
from sandbox.composition.vocabulary import DOCKER_VOCABULARY


# Record the context passed to the CLI without running a command.
def _record_cli(monkeypatch: pytest.MonkeyPatch, recorded: dict[str, Any]) -> None:
    # Replace the CLI group entry point with a recording double.
    def fake_cli(context: CliContext, *, console: Any = None, args: Sequence[str] | None = None) -> None:
        # Retain the injected context and argv.
        recorded["context"] = context
        recorded["args"] = args

    # Install the recording double.
    monkeypatch.setattr(composition_main, "cli_main", fake_cli)


# Verify the entry point builds the production presentation, factory, and vocabulary.
def test_main_injects_the_production_context(monkeypatch: pytest.MonkeyPatch) -> None:
    # Record the composition context instead of running Click.
    recorded: dict[str, Any] = {}
    _record_cli(monkeypatch, recorded)

    # Run the entry point with an explicit argv.
    composition_main.main(["--version"])

    # Require one context carrying the production values.
    context: CliContext = recorded["context"]
    assert recorded["args"] == ["--version"]
    assert context.vocabulary is DOCKER_VOCABULARY
    assert context.presentation.vocabulary is DOCKER_VOCABULARY
    assert isinstance(context.client_factory, SandboxClientFactory)
    assert context.client_factory.output is context.presentation.output


# Verify help, version, and completion construct no adapters and read no home.
def test_help_version_and_completions_construct_no_adapters_or_home(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail if any command path requests its client wiring.
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("help, version, and completion must not construct adapters or a home.")

    # Replace adapter construction and home resolution with failures.
    monkeypatch.setattr("sandbox.composition.client.build_docker_integrations", refuse)
    monkeypatch.setattr("sandbox.cli.context.default_home", refuse)

    # Check each inert entry path.
    for args in (["--version"], ["--help"], ["completions", "bash"]):
        # Click terminates the standalone command with its exit status.
        with pytest.raises(SystemExit) as raised:
            # Run the real CLI group through composition.
            composition_main.main(args)

        # Require success without touching adapters or the home.
        assert raised.value.code == 0
