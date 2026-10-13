"""Provide a repository-only microsandbox-shaped runtime fake for contract tests.

The fake models the seam shape a future microsandbox adapter must satisfy: an archive
artifact intake, read-only file secret deliveries, nullable observation facts, and
interactive shell status normalization. It is not a production adapter; composition is
the only place that could select it.
"""

# Imports.
from __future__ import annotations

from dataclasses import dataclass, field

# Import neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    EnsuredVolume,
    Initialization,
    Mount,
    MountSpec,
    Provenance,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRequirements,
    SandboxPlan,
    SandboxSpec,
    VolumeInfo,
    secret_target,
)

# Import typed errors.
from sandbox.errors import BoxNotFound, BoxNotReady, BoxNotRunning, NothingToRemove, VolumeInUse, VolumeNotFound
from sandbox.errors.secrets import SecretFileError
from sandbox.errors.capabilities import UnsupportedFeature

# Import the runtime preparation protocol and output values.
from sandbox.ports.output import SILENT, OutputSink
from sandbox.ports.runtime import RuntimePreparation, require_compatible_artifact

# Declare the fixed archive transport reference prefix.
REFERENCE_PREFIX: str = "sandbox-msb"


# Represent a microsandbox-shaped preparation token with neutral requirements.
@dataclass(frozen = True, slots = True)
class MicrosandboxPreparation:
    # Expose the neutral requirements a caller may read.
    requirements: RuntimeRequirements

    # Record the read-only secret file deliveries required by the runtime.
    secret_mounts: tuple[MountSpec, ...]

    # Keep the fake-owned plan behind the token.
    _plan: SandboxPlan = field(repr = False, compare = False)

    # Keep the fake-owned definition behind the token.
    _definition: RecipeDefinition = field(repr = False, compare = False)

    # Identify the owning fake runtime to reject foreign tokens.
    _owner: object = field(repr = False, compare = False)


# Implement the runtime port with a microsandbox-shaped archive and secret model.
class MicrosandboxShapedRuntime:
    # Construct a runtime with one effective UID and interactive status.
    def __init__(self, *, uid: int = 1000, enter_status: int = 0) -> None:
        # Require a nonnegative numeric UID.
        if type(uid) is not int or uid < 0:
            # Throw.
            raise ValueError("uid must be a nonnegative integer.")

        # Require an integer shell status.
        if type(enter_status) is not int:
            # Throw.
            raise ValueError("enter_status must be an integer.")

        # Store the configured facts and the mutable runtime state.
        self.uid: int = uid
        self.enter_status: int = enter_status
        self._boxes: dict[str, BoxObservation] = {}
        self._volumes: dict[str, VolumeInfo] = {}

    # Derive neutral requirements for one plan.
    def _requirements(self, plan: SandboxPlan) -> RuntimeRequirements:
        # Build the declared storage mounts.
        mounts: tuple[MountSpec, ...] = (
            MountSpec(kind = "bind", source = plan.workspace.host_directory, target = plan.workspace.target, read_only = False),
            *(MountSpec(kind = "volume", source = declaration.name, target = declaration.target, read_only = False) for declaration in plan.volumes),
        )

        # Build the effective sandbox facts without secret deliveries.
        spec: SandboxSpec = SandboxSpec(
            image = f"{REFERENCE_PREFIX}/{plan.project.name}:latest",
            platform = None,
            user = None,
            working_directory = plan.workspace.target,
            privileged = False,
            host_network = False,
            mounts = mounts,
        )

        # Require an archive intake, as a microsandbox adapter would.
        artifact: ArtifactRequirement = ArtifactRequirement(
            reference = spec.image,
            platform = None,
            transport = ArtifactTransport.DOCKER_ARCHIVE,
        )

        # Return the neutral requirements.
        return RuntimeRequirements(spec = spec, artifact = artifact)

    # Derive the read-only secret file deliveries for one plan.
    def _secret_mounts(self, plan: SandboxPlan) -> tuple[MountSpec, ...]:
        # Require every secret file to be readable before mutation.
        for secret in plan.secrets:
            # If the host file is missing or not a regular file.
            if not secret.host_path.is_file():
                # Throw the typed secret file failure.
                raise SecretFileError(secret.host_path, "does not exist or is not a regular file")

        # Derive one read-only delivery per bound secret.
        return tuple(
            MountSpec(kind = "bind", source = secret.host_path, target = secret_target(secret.alias), read_only = True)
            for secret in plan.secrets
        )

    # Verify the preparation token and artifact before mutation.
    def _accept(self, preparation: RuntimePreparation, artifact: BuildArtifact) -> MicrosandboxPreparation:
        # Reject a token this fake did not issue.
        if not isinstance(preparation, MicrosandboxPreparation) or preparation._owner is not self:
            # Throw a typed capability error.
            raise UnsupportedFeature("runtime-preparation", "The preparation token belongs to another runtime.")

        # Require the archive artifact to satisfy the neutral requirement.
        require_compatible_artifact(preparation.requirements.artifact, artifact)

        # Return the narrowed, verified token.
        return preparation

    # Resolve read-only runtime state and expose neutral requirements.
    def prepare(self, plan: SandboxPlan, definition: RecipeDefinition) -> MicrosandboxPreparation:
        # Derive the neutral requirements and secret deliveries.
        requirements: RuntimeRequirements = self._requirements(plan)
        secret_mounts: tuple[MountSpec, ...] = self._secret_mounts(plan)

        # Return the typed preparation token.
        return MicrosandboxPreparation(
            requirements = requirements,
            secret_mounts = secret_mounts,
            _plan = plan,
            _definition = definition,
            _owner = self,
        )

    # Plan the effective UID and declared volume targets without mutation.
    def plan_initialization(self, preparation: RuntimePreparation, artifact: BuildArtifact) -> Initialization:
        # Verify the token and archive before planning.
        token: MicrosandboxPreparation = self._accept(preparation, artifact)

        # Return the configured UID and every declared target.
        return Initialization(uid = self.uid, targets = tuple(declaration.target for declaration in token._plan.volumes))

    # Create one box from a verified archive without building or pulling.
    def create(
        self,
        preparation: RuntimePreparation,
        artifact: BuildArtifact,
        initialization: Initialization | None = None,
        *,
        output: OutputSink = SILENT,
    ) -> BoxObservation:
        # Verify the token and archive before mutation.
        token: MicrosandboxPreparation = self._accept(preparation, artifact)

        # Require every declared volume to be ensured first.
        for declaration in token._plan.volumes:
            # If the declared volume is missing.
            if declaration.name not in self._volumes:
                # Throw.
                raise VolumeNotFound(declaration.name)

        # Build the observed mounts from the workspace, volumes, and read-only secrets.
        mounts: tuple[Mount, ...] = (
            Mount(kind = "bind", source = str(token._plan.workspace.host_directory), target = token._plan.workspace.target),
            *(Mount(kind = "volume", source = declaration.name, target = declaration.target) for declaration in token._plan.volumes),
            *(Mount(kind = "bind", source = str(secret.host_path), target = secret_target(secret.alias)) for secret in token._plan.secrets),
        )

        # Build an observation with unavailable native facts left `None`.
        observation: BoxObservation = BoxObservation(
            name = token._plan.project.name,
            state = BoxState.RUNNING,
            provenance = Provenance(catalogue = token._definition.catalogue, recipe = token._definition.recipe),
            status_text = None,
            image = artifact.reference,
            working_directory = None,
            workspace = None,
            mounts = mounts,
            networks = None,
            backend = None,
        )

        # Record and return the observation.
        self._boxes[observation.name] = observation
        return observation

    # Observe one managed box by name, or report absence.
    def inspect(self, name: str) -> BoxObservation | None:
        # Return the observation or proven absence.
        return self._boxes.get(name)

    # List every managed box in name order.
    def list(self) -> tuple[BoxObservation, ...]:
        # Return the observations sorted by name.
        return tuple(self._boxes[name] for name in sorted(self._boxes))

    # Start an existing box and report whether this call changed its state.
    def start(self, name: str) -> bool:
        # Require the box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise BoxNotFound(name)

        # Refuse a partially created box before mutation.
        if observation.state is BoxState.CREATED:
            # Throw.
            raise BoxNotReady(name)

        # Report a no-op transition for a live box.
        if observation.state.is_live:
            # Return no change.
            return False

        # Transition to running.
        self._boxes[name] = BoxObservation(
            name = observation.name,
            state = BoxState.RUNNING,
            provenance = observation.provenance,
            status_text = None,
            image = observation.image,
            mounts = observation.mounts,
        )
        return True

    # Stop an existing box and report whether this call changed its state.
    def stop(self, name: str) -> bool:
        # Require the box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise BoxNotFound(name)

        # Report a no-op transition for a box that is not live.
        if not observation.state.is_live:
            # Return no change.
            return False

        # Transition to stopped.
        self._boxes[name] = BoxObservation(
            name = observation.name,
            state = BoxState.STOPPED,
            provenance = observation.provenance,
            status_text = None,
            image = observation.image,
            mounts = observation.mounts,
        )
        return True

    # Enter a live box and normalize the shell status.
    def enter(self, name: str, shell: str, login: bool) -> int:
        # Require a live box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise BoxNotFound(name)
        if not observation.state.is_live:
            # Throw.
            raise BoxNotRunning(name)

        # Preserve success and positive statuses and normalize signal termination.
        return self.enter_status if self.enter_status >= 0 else 1

    # Preview the resources removed with a box.
    def plan_removal(self, name: str) -> RemovalPlan:
        # Require an existing box.
        if name not in self._boxes:
            # Throw.
            raise NothingToRemove(name)

        # Return a preview without runtime references.
        return RemovalPlan(box = name, containers = (), networks = ())

    # Remove a box and its owned runtime resources by name.
    def remove(self, name: str) -> None:
        # Require an existing box.
        if name not in self._boxes:
            # Throw.
            raise NothingToRemove(name)

        # Delete the box; the fake reports no volume references.
        del self._boxes[name]

    # Ensure one declared shared volume exists.
    def ensure_volume(self, name: str) -> EnsuredVolume:
        # Reuse an existing volume without claiming creation.
        existing: VolumeInfo | None = self._volumes.get(name)
        if existing is not None:
            # Return the existing volume.
            return EnsuredVolume(info = existing, created = False)

        # Create a volume whose native facts are unavailable.
        info: VolumeInfo = VolumeInfo(name = name, driver = None, mountpoint = None, in_use_by = None)

        # Record the volume.
        self._volumes[name] = info
        return EnsuredVolume(info = info, created = True)

    # Observe one managed volume by name, or report absence.
    def inspect_volume(self, name: str) -> VolumeInfo | None:
        # Return the volume observation or proven absence.
        return self._volumes.get(name)

    # List every managed volume in name order.
    def list_volumes(self) -> tuple[VolumeInfo, ...]:
        # Return the volumes sorted by name.
        return tuple(self._volumes[name] for name in sorted(self._volumes))

    # Remove a managed shared volume by name.
    def remove_volume(self, name: str) -> None:
        # Require the volume.
        info: VolumeInfo | None = self._volumes.get(name)
        if info is None:
            # Throw.
            raise VolumeNotFound(name)

        # Refuse removal while a runtime instance references the volume.
        if info.in_use_by:
            # Throw.
            raise VolumeInUse(name)

        # Delete the volume.
        del self._volumes[name]


# Define the public API of the repository-only microsandbox fake.
__all__: list[str] = ["MicrosandboxPreparation", "MicrosandboxShapedRuntime"]
