# Imports.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace

# Import the neutral domain values.
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
    RuntimeRef,
    RuntimeRequirements,
    SandboxPlan,
    SandboxSpec,
    VolumeInfo,
    secret_target,
)

# Import the neutral errors.
from sandbox.errors import (
    BoxNotFound,
    BoxNotReady,
    BoxNotRunning,
    NothingToRemove,
    SandboxError,
    VolumeInUse,
    VolumeNotFound,
)
from sandbox.errors.capabilities import UnsupportedFeature

# Import the runtime preparation protocol and output port values.
from sandbox.ports.output import SILENT, OutputChannel, OutputSink
from sandbox.ports.runtime import RuntimePreparation, require_compatible_artifact


# Represent one recorded preparation request.
@dataclass(frozen = True, slots = True)
class RuntimePrepareRequest:
    # Record the neutral plan.
    plan: SandboxPlan

    # Record the opaque recipe source.
    definition: RecipeDefinition


# Represent one recorded initialization-planning request.
@dataclass(frozen = True, slots = True)
class InitializationRequest:
    # Record the returned preparation token.
    preparation: FakeRuntimePreparation

    # Record the accepted artifact.
    artifact: BuildArtifact


# Represent one recorded create request.
@dataclass(frozen = True, slots = True)
class CreateRequest:
    # Record the returned preparation token.
    preparation: FakeRuntimePreparation

    # Record the accepted artifact.
    artifact: BuildArtifact

    # Record the optional initialization.
    initialization: Initialization | None


# Represent one recorded interactive enter request.
@dataclass(frozen = True, slots = True)
class EnterRequest:
    # Record the box identity.
    name: str

    # Record the requested shell.
    shell: str

    # Report whether a login shell was requested.
    login: bool


# Represent a fake runtime-owned preparation token with neutral requirements.
@dataclass(frozen = True, slots = True)
class FakeRuntimePreparation:
    # Expose the neutral requirements the caller may read.
    requirements: RuntimeRequirements

    # Keep the fake-owned plan behind the token.
    _plan: SandboxPlan = field(repr = False, compare = False)

    # Keep the fake-owned opaque definition behind the token.
    _definition: RecipeDefinition = field(repr = False, compare = False)

    # Identify the owning fake runtime to reject foreign tokens.
    _owner: object = field(repr = False, compare = False)


# Represent a stateful fake runtime implementing the neutral port.
class FakeRuntime:
    # Construct a runtime with optional requirements and scenario facts.
    def __init__(
        self,
        *,
        requirements: RuntimeRequirements | None = None,
        uid: int = 1000,
        initialization_targets: tuple[str, ...] | None = None,
        enter_status: int = 0,
        create_output: tuple[tuple[OutputChannel, bytes], ...] = (),
        removal_plan: RemovalPlan | None = None,
    ) -> None:
        # Require a configured requirement when supplied.
        if requirements is not None and not isinstance(requirements, RuntimeRequirements):
            # Throw.
            raise ValueError("requirements must be a RuntimeRequirements value or `None`.")

        # Require a supported effective UID.
        if type(uid) is not int or uid < 0 or uid >= 2**32 - 1:
            # Throw.
            raise ValueError("uid must be an integer between `0` and `2**32 - 2`.")

        # Require configured initialization targets as an immutable tuple of strings.
        if initialization_targets is not None and (
            not isinstance(initialization_targets, tuple) or any(not isinstance(target, str) for target in initialization_targets)
        ):
            # Throw.
            raise ValueError("initialization_targets must be a tuple of strings or `None`.")

        # Require an integer shell status.
        if type(enter_status) is not int:
            # Throw.
            raise ValueError("enter_status must be an integer.")

        # Require typed child chunks.
        for chunk in create_output:
            # If the chunk is not a channel/bytes pair.
            if not isinstance(chunk, tuple) or len(chunk) != 2 or not isinstance(chunk[0], OutputChannel) or not isinstance(chunk[1], bytes):
                # Throw.
                raise ValueError("create_output must contain (OutputChannel, bytes) pairs.")

        # Require a typed removal preview when supplied.
        if removal_plan is not None and not isinstance(removal_plan, RemovalPlan):
            # Throw.
            raise ValueError("removal_plan must be a RemovalPlan value or `None`.")

        # Store the scenario configuration.
        self.requirements: RuntimeRequirements | None = requirements
        self.uid: int = uid
        self.initialization_targets: tuple[str, ...] | None = initialization_targets
        self.enter_status: int = enter_status
        self.create_output: tuple[tuple[OutputChannel, bytes], ...] = tuple(create_output)
        self.removal_plan: RemovalPlan | None = removal_plan

        # Create the mutable runtime state.
        self._boxes: dict[str, BoxObservation] = {}
        self._volumes: dict[str, VolumeInfo] = {}
        self._faults: deque[SandboxError] = deque()

        # Create the recorded request logs.
        self.prepare_requests: list[RuntimePrepareRequest] = []
        self.initialization_requests: list[InitializationRequest] = []
        self.create_requests: list[CreateRequest] = []
        self.enter_requests: list[EnterRequest] = []
        self.start_requests: list[str] = []
        self.stop_requests: list[str] = []
        self.removal_requests: list[str] = []
        self.remove_requests: list[str] = []
        self.ensure_volume_requests: list[str] = []
        self.remove_volume_requests: list[str] = []

    # Queue a port failure.
    def fail_next(self, error: SandboxError) -> None:
        # Require a neutral error.
        if not isinstance(error, SandboxError):
            # Throw a programming error.
            raise ValueError("Faults must be neutral sandbox errors.")

        # Record the failure.
        self._faults.append(error)

    # Seed a box observation for lifecycle tests.
    def add_box(self, observation: BoxObservation) -> None:
        # Require a box observation.
        if not isinstance(observation, BoxObservation):
            # Throw.
            raise ValueError("observation must be a BoxObservation value.")

        # Record the observation.
        self._boxes[observation.name] = observation

    # Seed a volume observation for table and removal tests.
    def add_volume(
        self,
        name: str,
        *,
        driver: str | None = "local",
        mountpoint: str | None = None,
        in_use_by: tuple[RuntimeRef, ...] | None = (),
    ) -> VolumeInfo:
        # Build the volume observation with the supplied display facts.
        info: VolumeInfo = VolumeInfo(name = name, driver = driver, mountpoint = mountpoint, in_use_by = in_use_by)

        # Record the observation.
        self._volumes[name] = info

        # Return the seeded observation.
        return info

    # Apply a queued fault before the next port operation.
    def _begin(self) -> None:
        # If a fault is queued.
        if self._faults:
            # Raise the next fault.
            raise self._faults.popleft()

    # Derive realistic neutral requirements for a plan.
    def _derive_requirements(self, plan: SandboxPlan) -> RuntimeRequirements:
        # Build the effective mounts from the workspace and declared volumes.
        mounts: list[MountSpec] = [
            MountSpec(kind = "bind", source = plan.workspace.host_directory, target = plan.workspace.target, read_only = False),
            *(MountSpec(kind = "volume", source = declaration.name, target = declaration.target, read_only = False) for declaration in plan.volumes),
        ]

        # Build the neutral spec.
        spec: SandboxSpec = SandboxSpec(
            image = f"sandbox/{plan.project.name}:latest",
            platform = None,
            user = None,
            working_directory = plan.workspace.target,
            privileged = False,
            host_network = False,
            mounts = tuple(mounts),
        )

        # Require a local image by default.
        artifact: ArtifactRequirement = ArtifactRequirement(
            reference = spec.image,
            platform = None,
            transport = ArtifactTransport.LOCAL_IMAGE,
        )

        # Return the neutral requirements.
        return RuntimeRequirements(spec = spec, artifact = artifact)

    # Verify the preparation token and artifact before any mutation.
    def _accept(self, preparation: RuntimePreparation, artifact: BuildArtifact) -> FakeRuntimePreparation:
        # Reject a token this fake did not issue.
        if not isinstance(preparation, FakeRuntimePreparation) or preparation._owner is not self:
            # Throw a typed capability error.
            raise UnsupportedFeature("runtime-preparation", "The preparation token belongs to another runtime.")

        # Require the artifact to satisfy the neutral requirement before mutation.
        require_compatible_artifact(preparation.requirements.artifact, artifact)

        # Return the narrowed, verified token.
        return preparation

    # Resolve read-only runtime state and expose neutral requirements.
    def prepare(self, plan: SandboxPlan, definition: RecipeDefinition) -> FakeRuntimePreparation:
        # Apply any queued fault and record the request.
        self._begin()
        self.prepare_requests.append(RuntimePrepareRequest(plan = plan, definition = definition))

        # Use configured requirements or derive a plausible effective set.
        requirements: RuntimeRequirements = self.requirements if self.requirements is not None else self._derive_requirements(plan)

        # Return the typed preparation token.
        return FakeRuntimePreparation(requirements = requirements, _plan = plan, _definition = definition, _owner = self)

    # Plan the effective UID and eligible volume targets without mutation.
    def plan_initialization(self, preparation: RuntimePreparation, artifact: BuildArtifact) -> Initialization:
        # Apply any queued fault and verify the token and artifact.
        self._begin()
        token: FakeRuntimePreparation = self._accept(preparation, artifact)
        self.initialization_requests.append(InitializationRequest(preparation = token, artifact = artifact))

        # Select the configured targets or every declared volume target.
        targets: tuple[str, ...] = (
            self.initialization_targets
            if self.initialization_targets is not None
            else tuple(declaration.target for declaration in token._plan.volumes)
        )

        # Return the neutral initialization.
        return Initialization(uid = self.uid, targets = targets)

    # Create and start one box from a prepared artifact.
    def create(
        self,
        preparation: RuntimePreparation,
        artifact: BuildArtifact,
        initialization: Initialization | None = None,
        *,
        output: OutputSink = SILENT,
    ) -> BoxObservation:
        # Apply any queued fault and verify the token and artifact.
        self._begin()
        token: FakeRuntimePreparation = self._accept(preparation, artifact)

        # Require every declared volume to be ensured before creation.
        for declaration in token._plan.volumes:
            # If the declared volume does not exist.
            if declaration.name not in self._volumes:
                # Throw.
                raise VolumeNotFound(declaration.name)

        # Record the accepted request.
        self.create_requests.append(CreateRequest(preparation = token, artifact = artifact, initialization = initialization))

        # Build the observed mounts from the plan and its read-only secret deliveries.
        mounts: list[Mount] = [
            Mount(kind = "bind", source = str(token._plan.workspace.host_directory), target = token._plan.workspace.target),
            *(Mount(kind = "volume", source = declaration.name, target = declaration.target) for declaration in token._plan.volumes),
            *(Mount(kind = "bind", source = str(secret.host_path), target = secret_target(secret.alias)) for secret in token._plan.secrets),
        ]

        # Build the display reference for this fake runtime instance.
        backend: RuntimeRef = RuntimeRef(id = f"fake-{token._plan.project.name}", name = token._plan.project.name)

        # Build the post-create observation.
        observation: BoxObservation = BoxObservation(
            name = token._plan.project.name,
            state = BoxState.RUNNING,
            provenance = Provenance(catalogue = token._definition.catalogue, recipe = token._definition.recipe),
            status_text = "running",
            image = artifact.reference,
            working_directory = token.requirements.spec.working_directory,
            workspace = token._plan.workspace,
            mounts = tuple(mounts),
            networks = (),
            backend = backend,
        )

        # Record the volume references held by the new box.
        for declaration in token._plan.volumes:
            # Read the ensured volume.
            info: VolumeInfo = self._volumes[declaration.name]

            # Append the holder when references are available.
            if info.in_use_by is not None:
                # Record the new reference.
                self._volumes[declaration.name] = replace(info, in_use_by = (*info.in_use_by, backend))

        # Forward the configured child output through the sink.
        for channel, data in self.create_output:
            # Preserve the original channel and exact bytes.
            output.process_output(channel, data)

        # Store the box and return the observation.
        self._boxes[observation.name] = observation
        return observation

    # Observe one managed box by name, or report absence.
    def inspect(self, name: str) -> BoxObservation | None:
        # Apply any queued fault and return the observation.
        self._begin()
        return self._boxes.get(name)

    # List every managed box in name order.
    def list(self) -> tuple[BoxObservation, ...]:
        # Apply any queued fault and return the observations in name order.
        self._begin()
        return tuple(self._boxes[name] for name in sorted(self._boxes))

    # Start an existing box and report whether this call changed its state.
    def start(self, name: str) -> bool:
        # Apply any queued fault and record the request.
        self._begin()
        self.start_requests.append(name)

        # Require an existing box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise BoxNotFound(name)

        # Refuse a partially created box before mutation.
        if observation.state is BoxState.CREATED:
            # Throw.
            raise BoxNotReady(name)

        # Report the no-op transition for a live box.
        if observation.state.is_live:
            # Return no change.
            return False

        # Transition to running.
        self._boxes[name] = replace(observation, state = BoxState.RUNNING)
        return True

    # Stop an existing box and report whether this call changed its state.
    def stop(self, name: str) -> bool:
        # Apply any queued fault and record the request.
        self._begin()
        self.stop_requests.append(name)

        # Require an existing box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise BoxNotFound(name)

        # Report the no-op transition for a box that is not live.
        if not observation.state.is_live:
            # Return no change.
            return False

        # Transition to stopped.
        self._boxes[name] = replace(observation, state = BoxState.STOPPED)
        return True

    # Enter a live box and return the shell exit status.
    def enter(self, name: str, shell: str, login: bool) -> int:
        # Apply any queued fault and record the request.
        self._begin()
        self.enter_requests.append(EnterRequest(name = name, shell = shell, login = login))

        # Require an existing live box.
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
        # Apply any queued fault and record the request.
        self._begin()
        self.removal_requests.append(name)

        # Require an existing box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise NothingToRemove(name)

        # Return the configured preview or a default derived from the observation.
        if self.removal_plan is not None:
            # Return the configured preview.
            return self.removal_plan

        # Return the neutral preview.
        return RemovalPlan(
            box = name,
            containers = () if observation.backend is None else (observation.backend,),
            networks = (),
        )

    # Remove a box and its owned runtime resources by name.
    def remove(self, name: str) -> None:
        # Apply any queued fault and record the request.
        self._begin()
        self.remove_requests.append(name)

        # Require an existing box.
        observation: BoxObservation | None = self._boxes.get(name)
        if observation is None:
            # Throw.
            raise NothingToRemove(name)

        # Release every volume reference held by this box.
        for mount in observation.mounts or ():
            # If the mount uses a known managed volume.
            if mount.kind == "volume" and mount.source in self._volumes and observation.backend is not None:
                # Read the volume and drop this holder.
                info: VolumeInfo = self._volumes[mount.source]
                if info.in_use_by is not None:
                    # Record the remaining references.
                    self._volumes[mount.source] = replace(info, in_use_by = tuple(reference for reference in info.in_use_by if reference != observation.backend))

        # Delete the box.
        del self._boxes[name]

    # Ensure one declared shared volume exists.
    def ensure_volume(self, name: str) -> EnsuredVolume:
        # Apply any queued fault and require a physical volume name.
        self._begin()
        if not isinstance(name, str) or not name.strip():
            # Throw.
            raise ValueError("name must be a nonblank physical volume name.")

        # Record the request.
        self.ensure_volume_requests.append(name)

        # Reuse an existing volume without claiming creation.
        existing: VolumeInfo | None = self._volumes.get(name)
        if existing is not None:
            # Return the existing volume.
            return EnsuredVolume(info = existing, created = False)

        # Create a local volume with no holders.
        info: VolumeInfo = VolumeInfo(
            name = name,
            driver = "local",
            mountpoint = f"/var/lib/docker/volumes/{name}/_data",
            in_use_by = (),
        )

        # Record the volume.
        self._volumes[name] = info
        return EnsuredVolume(info = info, created = True)
