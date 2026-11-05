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

    # Accept the composition factory plus direct test injections.
    def __init__(
        self,
        presentation: CliPresentation | None = None,
        errors: ErrorPresenter | None = None,
        *,
        client_factory: ClientFactory | None = None,
        console: Any | None = None,
        vocabulary: RuntimeVocabulary | None = None,
    ) -> None:
        # Retain the composition-supplied factory after protocol validation.
        if client_factory is not None and not isinstance(client_factory, ClientFactory):
            # Throw a programming error for an unusable injection.
            raise TypeError("client_factory must implement ClientFactory.")

        # Retain the resolved factory.
        self.client_factory = client_factory

        # Prefer the explicit console, then the supplied presentation.
        selected_console: Any | None = console if console is not None else (presentation.err if presentation is not None else None)

        # Resolve the vocabulary from explicit input, errors, or presentation.
        selected_vocabulary: RuntimeVocabulary = (
            vocabulary
            or (errors.vocabulary if errors is not None else None)
            or (presentation.vocabulary if presentation is not None else None)
            or DOCKER_VOCABULARY
        )

        # Retain the resolved vocabulary and console.
        self.console = selected_console
        self.vocabulary = selected_vocabulary

        # Construct the presentation when one was not injected.
        self.presentation = presentation if presentation is not None else CliPresentation.attach(vocabulary = selected_vocabulary, console = selected_console)

        # Bind the single presenter to the same console and vocabulary.
        self.errors = errors if errors is not None else ErrorPresenter(selected_vocabulary, console = self.presentation.err)
