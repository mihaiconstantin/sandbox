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

    # Create and start a box from a registered catalogue recipe.
    def create(self, request: CreateBoxRequest) -> CreateBoxResult:
        # Require the public request value.
        if not isinstance(request, CreateBoxRequest):
            # Throw a programming error for Python API misuse.
            raise TypeError("request must be a CreateBoxRequest.")

        # Validate identifiers before touching configuration or a port.
        validate_identifier(request.project, "project")
        validate_identifier(request.catalogue, "catalogue")

        # Resolve the project directory before any engine call.
        project_dir: Path = self._resolve_project_dir(request.project_dir)

        # Resolve the selected catalogue recipe and its registered directory.
        recipe: ResolvedCatalogueRecipe = self._catalogues.resolve_recipe(request.catalogue, request.recipe)
        catalogue_root: Path = self._catalogues.locate(request.catalogue)

        # Resolve every secret required by the selected recipe.
        secrets: list[Secret] = []

        # Declare the required secret alias.
        alias: str

        # For each required secret.
        for alias in recipe.secrets:
            # Read the validated catalogue-scoped binding.
            binding: SecretBinding | None = self._secrets.get(request.catalogue, alias)

            # If the secret has no user binding.
            if binding is None:
                # Throw with the current catalogue, alias, and recipe facts.
                raise MissingSecret(request.catalogue, alias, recipe.name)

            # Record the resolved host file.
            secrets.append(Secret(alias = binding.alias, host_path = binding.host_path))

        # Build the neutral plan from the project and resolved recipe.
        plan: SandboxPlan = SandboxPlan(
            project = Project(name = request.project, directory = project_dir),
            workspace = Workspace(host_directory = project_dir, target = project_target(request.project)),
            volumes = tuple(
                VolumeDeclaration(name = volume.name, scope = volume.scope, target = volume.target)
                for volume in recipe.volumes
            ),
            secrets = tuple(secrets),
            allow_root = recipe.allow_root,
        )

        # Build the opaque definition from the parent-first recipe files and service selector.
        definition: RecipeDefinition = RecipeDefinition(
            catalogue = request.catalogue,
            recipe = recipe.name,
            catalogue_root = catalogue_root,
            files = recipe.compose,
            service = recipe.service,
        )

        # Resolve read-only runtime state and expose neutral requirements.
        preparation: RuntimePreparation = self._runtime.prepare(plan, definition)

        # Read the neutral requirements the runtime exposes.
        requirements: RuntimeRequirements = preparation.requirements

        # Validate neutral policy before any image or volume mutation.
        validate_spec(plan, requirements.spec, catalogue_root = catalogue_root)

        # Track the prepared artifact and the operation-scoped staging directory.
        artifact: BuildArtifact | None = None
        staging_dir: Path | None = None

        # Prepare the image, ensure volumes, plan initialization, and create the box.
        try:
            # Create operation-scoped staging for a byte-carrying transport.
            if requirements.artifact.transport is not ArtifactTransport.LOCAL_IMAGE:
                # Create the caller-owned staging directory.
                staging_dir = Path(tempfile.mkdtemp(prefix = "sandbox-artifact-"))

            # Report the image phase before the builder can build or pull.
            self._output.progress(ProgressPhase.PREPARE_IMAGE, subject = requirements.artifact.reference)

            # Ensure the required image exists and obtain the typed artifact.
            artifact = self._builder.prepare(
                plan,
                definition,
                requirements.artifact,
                rebuild = request.rebuild,
                staging_dir = staging_dir,
                output = self._output,
            )

            # Require the artifact to satisfy the runtime requirement before volume mutation.
            require_compatible_artifact(requirements.artifact, artifact)

            # Ensure each declared shared volume in plan order.
            for declaration in plan.volumes:
                # Report the volume phase before the runtime call.
                self._output.progress(ProgressPhase.ENSURE_VOLUME, subject = declaration.name)

                # Create the volume when absent and reuse it when present.
                self._runtime.ensure_volume(declaration.name)

            # Plan the effective UID and eligible volume targets without mutation.
            initialization: Initialization = self._runtime.plan_initialization(preparation, artifact)

            # Apply the root and initialization policy on every create path.
            validate_initialization(plan, initialization, mounts = requirements.spec.mounts)

            # Report the create phase before the runtime mutation.
            self._output.progress(ProgressPhase.CREATE, subject = plan.project.name)

            # Start from the prepared artifact without an implicit build or pull.
            observation: BoxObservation = self._runtime.create(
                preparation,
                artifact,
                initialization,
                output = self._output,
            )

            # Return the effective recipe and the observed box.
            return CreateBoxResult(recipe = recipe.name, box = observation)

        # Always remove operation-scoped artifact staging.
        finally:
            # Remove the archive before its staging directory.
            self._remove_artifact(artifact)

            # Remove the staging directory when one was created.
            if staging_dir is not None:
                # Remove the staging tree best-effort without masking the operation result.
                shutil.rmtree(staging_dir, ignore_errors = True)

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


# Define the public API of the `sandbox.sdk.boxes` module.
__all__: list[str] = ["BoxOperations"]
