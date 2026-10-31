# Imports.
from __future__ import annotations

from dataclasses import dataclass

# Import the observed box value.
from sandbox.domain.observation import BoxObservation


# Report the effective recipe and the box observed after creation.
@dataclass(frozen = True, slots = True)
class CreateBoxResult:
    # Record the selected effective recipe name.
    recipe: str

    # Record the observed box.
    box: BoxObservation

    def __post_init__(self) -> None:
        # Require the effective recipe identity.
        if not isinstance(self.recipe, str) or not self.recipe.strip():
            # Throw.
            raise ValueError("CreateBoxResult.recipe must be a nonblank string.")

        # Require a post-create observation.
        if not isinstance(self.box, BoxObservation):
            # Throw.
            raise ValueError("CreateBoxResult.box must be a BoxObservation value.")
