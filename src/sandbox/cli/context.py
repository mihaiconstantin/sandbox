# Imports.
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import click

# Import the public SDK client and output contract.
from sandbox.ports.output import SILENT, OutputSink
from sandbox.sdk import SandboxClient

# Import the public error root.
from sandbox.errors.base import SandboxError

# Import the CLI presentation values.
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.vocabulary import DOCKER_VOCABULARY, RuntimeVocabulary


# Represent the composition-supplied factory that builds one client per home.
@runtime_checkable
class ClientFactory(Protocol):
    # Build a client bound to one configuration home and presentation sink.
    def for_home(self, home: Path, *, output: OutputSink = SILENT) -> SandboxClient: ...


# Bind the client factory, presentation, and error presenter for one invocation.
@dataclass(init = False)
class CliContext:
    # Hold the optional composition-supplied client factory.
    client_factory: ClientFactory | None = None

    # Hold an explicitly injected stderr console, if any.
    console: Any | None = None

    # Hold the runtime vocabulary used for labels and backend nouns.
    vocabulary: RuntimeVocabulary = DOCKER_VOCABULARY

    # Hold the per-invocation presentation and its output sink.
    presentation: CliPresentation = field(init = False)

    # Hold the single error presenter.
    errors: ErrorPresenter = field(init = False)
