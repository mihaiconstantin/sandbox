# Imports.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Represent one request to create and start a box from a catalogue recipe.
@dataclass(frozen = True, slots = True)
class CreateBoxRequest:
    # Identify the project and its box.
    project: str

    # Record the host project directory.
    project_dir: Path

    # Select the registered catalogue.
    catalogue: str

    # Select a recipe, or use the catalogue default when absent.
    recipe: str | None = None

    # Rebuild a buildable recipe image even when it already exists.
    rebuild: bool = False

    def __post_init__(self) -> None:
        # Require the project identity.
        if not isinstance(self.project, str) or not self.project.strip():
            # Throw.
            raise ValueError("CreateBoxRequest.project must be a nonblank string.")

        # Require a host project directory.
        if not isinstance(self.project_dir, Path):
            # Throw.
            raise ValueError("CreateBoxRequest.project_dir must be a path.")

        # Require the selected catalogue.
        if not isinstance(self.catalogue, str) or not self.catalogue.strip():
            # Throw.
            raise ValueError("CreateBoxRequest.catalogue must be a nonblank string.")

        # If a recipe was selected.
        if self.recipe is not None:
            # Require a nonblank recipe name.
            if not isinstance(self.recipe, str) or not self.recipe.strip():
                # Throw.
                raise ValueError("CreateBoxRequest.recipe must be a nonblank string or `None`.")

        # Require exact rebuild intent.
        if type(self.rebuild) is not bool:
            # Throw.
            raise ValueError("CreateBoxRequest.rebuild must be a Boolean.")


# Define the public API of the `sandbox.sdk.requests` module.
__all__: list[str] = ["CreateBoxRequest"]
