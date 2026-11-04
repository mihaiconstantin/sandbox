# Imports.
from __future__ import annotations

from dataclasses import dataclass


# Represent the backend display vocabulary supplied by the composition root.
@dataclass(frozen = True, slots = True)
class RuntimeVocabulary:
    # Identify the neutral backend key carried by public errors.
    backend: str

    # Display the backend title used in prose.
    title: str

    # Display the backticked tool name used in compatibility messages.
    tool: str

    # Display the singular resource noun.
    noun: str

    # Display the plural resource noun.
    plural: str

    # Require meaningful display values.
    def __post_init__(self) -> None:
        # Require every vocabulary part to be a nonblank string.
        for field_name, value in (
            ("backend", self.backend),
            ("title", self.title),
            ("tool", self.tool),
            ("noun", self.noun),
            ("plural", self.plural),
        ):
            # If the value is missing.
            if not isinstance(value, str) or not value.strip():
                # Throw.
                raise ValueError(f"RuntimeVocabulary.{field_name} must be a nonblank string.")

    # Render the capitalized resource label used by the status report.
    @property
    def label(self) -> str:
        # Capitalize the configured scalar noun.
        return self.noun.capitalize()


# Define the Docker defaults used by direct Click invocations without composition.
DOCKER_VOCABULARY: RuntimeVocabulary = RuntimeVocabulary(
    backend = "docker",
    title = "Docker",
    tool = "`docker`",
    noun = "container",
    plural = "containers",
)


# Keep the neutral alias for callers that name the fallback explicitly.
NEUTRAL_VOCABULARY: RuntimeVocabulary = DOCKER_VOCABULARY


# Define the public API of the `sandbox.cli.presentation.vocabulary` module.
__all__: list[str] = ["DOCKER_VOCABULARY", "NEUTRAL_VOCABULARY", "RuntimeVocabulary"]
