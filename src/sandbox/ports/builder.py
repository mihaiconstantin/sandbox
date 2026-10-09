# Imports.
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

# Import the neutral domain values.
from sandbox.domain import ArtifactRequirement, BuildArtifact, RecipeDefinition, SandboxPlan

# Import the neutral output sink and its silent default.
from sandbox.ports.output import SILENT, OutputSink


# Represent the port that prepares a typed build artifact for a runtime requirement.
@runtime_checkable
class Builder(Protocol):
    # Ensure the required image exists and return the typed artifact.
    def prepare(
        self,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        *,
        rebuild: bool = False,
        staging_dir: Path | None = None,
        output: OutputSink = SILENT,
    ) -> BuildArtifact: ...


# Define the public API of the `sandbox.ports.builder` module.
__all__: list[str] = ["Builder"]
