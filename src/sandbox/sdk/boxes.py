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

    # List every managed box in name order.
    def list(self) -> tuple[BoxObservation, ...]:
        # Return the observations sorted by box name.
        return tuple(sorted(self._runtime.list(), key = lambda observation: observation.name))

    # Start an existing box and report whether this call changed its state.
    def start(self, name: str) -> bool:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Report the start phase even for a no-op transition.
        self._output.progress(ProgressPhase.START, subject = name)

        # Delegate the observed-state policy to the runtime.
        return self._runtime.start(name)

    # Stop an existing box and report whether this call changed its state.
    def stop(self, name: str) -> bool:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Report the stop phase even for a no-op transition.
        self._output.progress(ProgressPhase.STOP, subject = name)

        # Delegate the observed-state policy to the runtime.
        return self._runtime.stop(name)

    # Enter a live box and return the shell exit status.
    def enter(self, name: str, *, shell: str, login: bool) -> int:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Delegate the interactive shell without SDK terminal policy or output.
        return self._runtime.enter(name, shell, login)

    # Preview the runtime resources removed with a box.
    def plan_removal(self, name: str) -> RemovalPlan:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Return the read-only removal preview.
        return self._runtime.plan_removal(name)

    # Remove a box and its owned runtime resources.
    def remove(self, name: str) -> None:
        # Reject an invalid project name before reaching the runtime.
        validate_identifier(name, "project")

        # Report the removal phase before the runtime call.
        self._output.progress(ProgressPhase.REMOVE, subject = name)

        # Apply the runtime removal policy and postcondition.
        self._runtime.remove(name)

    # Resolve one host project directory without leaking raw filesystem errors.
    def _resolve_project_dir(self, directory: Path) -> Path:
        # Resolve the project directory to an absolute existing path.
        try:
            resolved: Path = directory.expanduser().resolve(strict = True)

        # If the directory cannot be resolved.
        except OSError as error:
            # Throw a typed configuration error.
            raise ConfigurationError("project_dir", f"Project directory `{directory}` cannot be resolved: {error}.") from error

        # If the resolved path is not a directory.
        if not resolved.is_dir():
            # Throw.
            raise ConfigurationError("project_dir", f"Project directory `{resolved}` is not a directory.")

        # Return the resolved project directory.
        return resolved

    # Remove the prepared archive when one was written.
    def _remove_artifact(self, artifact: BuildArtifact | None) -> None:
        # If no archive was written.
        if artifact is None or artifact.archive_path is None:
            # Return.
            return

        # Remove the operation-scoped archive without masking the operation result.
        try:
            # Delete the archive if it still exists.
            artifact.archive_path.unlink(missing_ok = True)

        # Ignore cleanup filesystem failures.
        except OSError:
            # Leave the best-effort cleanup silent.
            return
