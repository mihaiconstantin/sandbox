# Imports.
from __future__ import annotations

from collections.abc import Sequence

# Import the CLI entry point and its per-invocation context.
from sandbox.cli.context import CliContext
from sandbox.cli.group import main as cli_main
from sandbox.cli.presentation.console import CliPresentation

# Import the composition-owned factory and vocabulary.
from sandbox.composition.client import SandboxClientFactory
from sandbox.composition.vocabulary import DOCKER_VOCABULARY


# Build the inert production CLI context for one invocation.
def build_context() -> CliContext:
    # Construct the one stderr presentation selected by composition.
    presentation: CliPresentation = CliPresentation.attach(vocabulary = DOCKER_VOCABULARY)

    # Build the factory without constructing an adapter or reading a home.
    factory: SandboxClientFactory = SandboxClientFactory(output = presentation.output)

    # Inject the production factory, presentation, and runtime vocabulary.
    return CliContext(
        presentation = presentation,
        client_factory = factory,
        vocabulary = DOCKER_VOCABULARY,
    )


# Run the production CLI with composition-owned presentation and client wiring.
def main(argv: Sequence[str] | None = None) -> None:
    # Build the inert context once for this invocation.
    context: CliContext = build_context()

    # Preserve the plain entry-point call when no explicit argv is supplied.
    if argv is None:
        # Delegate to the single CLI entry point.
        cli_main(context)
    else:
        # Delegate with an explicit argv for tests and embedding.
        cli_main(context, args = argv)


# If the script is run directly.
if __name__ == "__main__":
    # Run the production CLI.
    main()


# Define the public API of the `sandbox.composition.main` module.
__all__: list[str] = ["build_context", "main"]
