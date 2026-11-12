# Imports.
from __future__ import annotations

# Import the presentation vocabulary value.
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary


# Define the Docker runtime vocabulary selected by composition.
DOCKER_VOCABULARY: RuntimeVocabulary = RuntimeVocabulary(
    backend = "docker",
    title = "Docker",
    tool = "`docker`",
    noun = "container",
    plural = "containers",
)


# Define the public API of the `sandbox.composition.vocabulary` module.
__all__: list[str] = ["DOCKER_VOCABULARY"]
