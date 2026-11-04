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
