# Imports.
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

# Import the neutral artifact and plan values.
from sandbox.catalogue.resolve import ResolvedCatalogueRecipe
from sandbox.domain.artifact import ArtifactTransport, BuildArtifact
from sandbox.domain.observation import BoxObservation, RemovalPlan
from sandbox.domain.paths import project_target
from sandbox.domain.plan import Initialization, Project, RecipeDefinition, SandboxPlan, Secret, Workspace
from sandbox.domain.registry import SecretBinding
from sandbox.domain.requirements import RuntimeRequirements
from sandbox.domain.volume import VolumeDeclaration

# Import neutral policy.
from sandbox.policy.initialization import validate_initialization
from sandbox.policy.spec import validate_spec

# Import the neutral ports and phase vocabulary.
from sandbox.ports.builder import Builder
from sandbox.ports.output import OutputSink, ProgressPhase
from sandbox.ports.runtime import Runtime, RuntimePreparation, require_compatible_artifact

# Import typed public errors.
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.secrets import MissingSecret

# Import the shared identifier rule.
from sandbox.validation.identifiers import validate_identifier

# Import the SDK catalogue, secret, request, and result values.
from sandbox.sdk.catalogues import CatalogueOperations
from sandbox.sdk.requests import CreateBoxRequest
from sandbox.sdk.results import CreateBoxResult
from sandbox.sdk.secrets import SecretOperations


# Expose box creation and lifecycle use cases over the neutral ports.
class BoxOperations:
    # Bind the operations to their ports, configuration operations, and output sink.
    def __init__(
        self,
        runtime: Runtime,
        builder: Builder,
        catalogues: CatalogueOperations,
        secrets: SecretOperations,
        output: OutputSink,
    ) -> None:
        # Retain the ports and the advisory sink.
        self._runtime: Runtime = runtime
        self._builder: Builder = builder
        self._catalogues: CatalogueOperations = catalogues
        self._secrets: SecretOperations = secrets
        self._output: OutputSink = output

    # Observe one managed box by name, or report proven absence.
    def get(self, name: str) -> BoxObservation | None:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Return the observed box or the proven absence.
        return self._runtime.inspect(name)
