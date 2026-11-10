# Import the CLI presentation surface.
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.output import CliOutput
from sandbox.cli.presentation.table import TableRenderer, render_table
from sandbox.cli.presentation.vocabulary import DOCKER_VOCABULARY, NEUTRAL_VOCABULARY, RuntimeVocabulary

# Define the public API of the `sandbox.cli.presentation` package.
__all__: list[str] = [
    "DOCKER_VOCABULARY",
    "CliOutput",
    "CliPresentation",
    "ErrorPresenter",
    "NEUTRAL_VOCABULARY",
    "RuntimeVocabulary",
    "TableRenderer",
    "render_table",
]
