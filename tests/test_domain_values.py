"""Verify the neutral domain package and its value invariants."""

# Imports.
import dataclasses
from pathlib import Path

# Import pytest for value assertions.
import pytest

# Import the domain package and its dedicated modules.
import sandbox.domain
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BoxObservation,
    BoxState,
    BuildArtifact,
    CatalogueBinding,
    CatalogueRegistration,
    CatalogueRemovalPlan,
    EnsuredVolume,
    Initialization,
    Mount,
    MountSpec,
    Network,
    Project,
    Provenance,
    RecipeDefinition,
    RemovalPlan,
    RuntimeRef,
    RuntimeRequirements,
    SandboxPlan,
    SandboxSpec,
    Secret,
    SecretBinding,
    VolumeDeclaration,
    VolumeInfo,
    Workspace,
)
from sandbox.domain import artifact, mount, observation, paths, plan, registry, requirements, volume

# Declare every name the final domain package exports.
DOMAIN_NAMES: tuple[str, ...] = (
    "ArtifactRequirement",
    "ArtifactTransport",
    "BoxObservation",
    "BoxState",
    "BuildArtifact",
    "CatalogueBinding",
    "CatalogueRegistration",
    "CatalogueRemovalPlan",
    "EnsuredVolume",
    "Initialization",
    "Mount",
    "MountSpec",
    "Network",
    "PROJECT_ROOT",
    "Project",
    "Provenance",
    "RecipeDefinition",
    "RemovalPlan",
    "RuntimeRef",
    "RuntimeRequirements",
    "SECRET_ROOT",
    "SandboxPlan",
    "SandboxSpec",
    "Secret",
    "SecretBinding",
    "VolumeDeclaration",
    "VolumeInfo",
    "Workspace",
    "project_target",
    "secret_target",
)


# Verify the package exports only the final names and groups values in dedicated modules.
def test_package_exports_final_names_and_module_placement() -> None:
    # Require exactly the final package-level names.
    assert set(sandbox.domain.__all__) == set(DOMAIN_NAMES)
    for name in DOMAIN_NAMES:
        # Compare each exported name.
        assert hasattr(sandbox.domain, name), name

    # Require the retired architecture values to stay absent.
    for retired in (
        "Box",
        "BoxIntent",
        "BuildPolicy",
        "Catalogue",
        "Recipe",
        "ResolvedBuild",
        "ResolvedHook",
        "ResolvedHooks",
        "ResolvedMount",
        "ResolvedNetwork",
        "ResolvedRecipe",
        "Sandbox",
        "Volume",
    ):
        assert not hasattr(sandbox.domain, retired), retired

    # Compare the module placement of values shared with the final modules.
    assert plan.Project is Project
    assert plan.Workspace is Workspace
    assert plan.Secret is Secret
    assert plan.RecipeDefinition is RecipeDefinition
    assert plan.SandboxPlan is SandboxPlan
    assert plan.Initialization is Initialization
    assert observation.BoxState is BoxState
    assert observation.BoxObservation is BoxObservation
    assert observation.Provenance is Provenance
    assert observation.RuntimeRef is RuntimeRef
    assert volume.VolumeDeclaration is VolumeDeclaration
    assert volume.VolumeInfo is VolumeInfo
    assert volume.EnsuredVolume is EnsuredVolume
    assert mount.Mount is Mount
    assert mount.MountSpec is MountSpec
    assert mount.Network is Network
    assert artifact.ArtifactRequirement is ArtifactRequirement
    assert requirements.SandboxSpec is SandboxSpec
    assert registry.CatalogueRegistration is CatalogueRegistration

    # Compare the package constants and helpers.
    assert paths.PROJECT_ROOT == sandbox.domain.PROJECT_ROOT == "/projects"
    assert paths.SECRET_ROOT == "/run/secrets"
    assert paths.project_target("demo") == "/projects/demo"
    assert paths.secret_target("api_key") == "/run/secrets/api_key"

    # Reject nonblank inputs for the guest-target helpers.
    with pytest.raises(ValueError):
        paths.project_target("")

    with pytest.raises(ValueError):
        paths.secret_target(" ")


# Verify plans keep project identity, unique secrets, and immutable collections.
def test_plan_enforces_identity_and_unique_secret_aliases() -> None:
    # Build the fixed project and workspace values.
    project = Project(name = "demo", directory = Path("/work/demo"))
    workspace = Workspace(host_directory = Path("/work/demo"), target = "/projects/demo")
    secret = Secret(alias = "token", host_path = Path("/keys/token"))

    # Build a valid plan.
    value = SandboxPlan(project = project, workspace = workspace, volumes = (), secrets = (secret,), allow_root = False)

    # Compare the plan identity and binding.
    assert value.project.name == "demo"
    assert value.secrets == (secret,)

    # Reject a blank project name.
    with pytest.raises(ValueError):
        Project(name = " ", directory = Path("/work/demo"))

    # Reject a workspace target for a different project.
    with pytest.raises(ValueError):
        SandboxPlan(
            project = project,
            workspace = Workspace(host_directory = Path("/work/demo"), target = "/projects/other"),
            volumes = (),
            secrets = (),
            allow_root = False,
        )

    # Reject duplicate secret aliases.
    with pytest.raises(ValueError):
        SandboxPlan(project = project, workspace = workspace, volumes = (), secrets = (secret, secret), allow_root = False)

    # Reject mutable plan collections.
    with pytest.raises(ValueError):
        SandboxPlan(project = project, workspace = workspace, volumes = [], secrets = (), allow_root = False)  # pyright: ignore[reportArgumentType]

    # Reject a non-Boolean root policy.
    with pytest.raises(ValueError):
        SandboxPlan(project = project, workspace = workspace, volumes = (), secrets = (), allow_root = 1)  # pyright: ignore[reportArgumentType]


# Verify mount specs reject unsupported kinds and invalid guest targets.
def test_mount_spec_enforces_its_invariants() -> None:
    # Accept an absolute bind mount.
    spec = MountSpec(kind = "bind", source = Path("/work/demo"), target = "/projects/demo", read_only = False)

    # Compare the accepted mount declaration.
    assert (spec.kind, spec.source, spec.target, spec.read_only) == ("bind", Path("/work/demo"), "/projects/demo", False)

    # Reject an unmodelled mount kind.
    with pytest.raises(ValueError):
        MountSpec(kind = "tmpfs", source = "state", target = "/data", read_only = False)  # pyright: ignore[reportArgumentType]

    # Reject an absolute guest target requirement.
    with pytest.raises(ValueError):
        MountSpec(kind = "volume", source = "state", target = "data", read_only = False)

    # Reject a relative host bind source.
    with pytest.raises(ValueError):
        MountSpec(kind = "bind", source = Path("work/demo"), target = "/projects/demo", read_only = False)

    # Reject a non-Boolean read-only flag.
    with pytest.raises(ValueError):
        MountSpec(kind = "volume", source = "state", target = "/data", read_only = 1)  # pyright: ignore[reportArgumentType]


# Verify the sandbox spec carries only neutral effective facts.
def test_sandbox_spec_enforces_neutral_fields() -> None:
    # Build a complete sandbox spec.
    spec = SandboxSpec(
        image = "demo:latest",
        platform = "linux/arm64",
        user = 1000,
        working_directory = "/projects/demo",
        privileged = False,
        host_network = False,
        mounts = (
            MountSpec(kind = "bind", source = Path("/work/demo"), target = "/projects/demo", read_only = False),
        ),
    )

    # Compare the effective facts.
    assert spec.image == "demo:latest"
    assert spec.mounts[0].target == "/projects/demo"

    # Reject a blank image, platform, and working directory.
    for image, platform, working_directory in (
        ("", None, None),
        ("demo", " ", None),
        ("demo", None, "projects/demo"),
    ):
        # Require the invalid field combination to fail.
        with pytest.raises(ValueError):
            SandboxSpec(
                image = image,
                platform = platform,
                user = None,
                working_directory = working_directory,
                privileged = False,
                host_network = False,
                mounts = (),
            )

    # Reject an invalid user value and non-Boolean policy flags.
    with pytest.raises(ValueError):
        SandboxSpec(image = "demo", platform = None, user = -1, working_directory = None, privileged = False, host_network = False, mounts = ())

    with pytest.raises(ValueError):
        SandboxSpec(image = "demo", platform = None, user = None, working_directory = None, privileged = 0, host_network = False, mounts = ())  # pyright: ignore[reportArgumentType]

    # Reject a mutable mount collection.
    with pytest.raises(ValueError):
        SandboxSpec(
            image = "demo",
            platform = None,
            user = None,
            working_directory = None,
            privileged = False,
            host_network = False,
            mounts = [MountSpec(kind = "volume", source = "state", target = "/data", read_only = False)],  # pyright: ignore[reportArgumentType]
        )


# Verify runtime requirements join one spec and one artifact requirement.
def test_runtime_requirements_require_neutral_parts() -> None:
    # Build a complete requirement pair.
    value = RuntimeRequirements(
        spec = SandboxSpec(image = "demo", platform = None, user = None, working_directory = None, privileged = False, host_network = False, mounts = ()),
        artifact = ArtifactRequirement(reference = "demo:latest", platform = None, transport = ArtifactTransport.LOCAL_IMAGE),
    )

    # Compare the neutral parts.
    assert value.spec.image == "demo"
    assert value.artifact.transport is ArtifactTransport.LOCAL_IMAGE

    # Reject parts of the wrong type.
    with pytest.raises(ValueError):
        RuntimeRequirements(spec = "demo", artifact = value.artifact)  # pyright: ignore[reportArgumentType]

    with pytest.raises(ValueError):
        RuntimeRequirements(spec = value.spec, artifact = "demo")  # pyright: ignore[reportArgumentType]


# Verify artifact transports use the neutral closed vocabulary.
def test_artifact_transport_names_the_supported_transports() -> None:
    # Compare the stable transport values.
    assert ArtifactTransport.LOCAL_IMAGE == "local-image"
    assert ArtifactTransport.DOCKER_ARCHIVE == "docker-archive"
    assert ArtifactTransport.OCI_ARCHIVE == "oci-archive"


# Verify artifact requirements and artifacts enforce their invariants.
def test_artifact_values_enforce_their_invariants() -> None:
    # Build one valid local-image requirement and artifact.
    requirement = ArtifactRequirement(reference = "demo:latest", platform = "linux/arm64", transport = ArtifactTransport.LOCAL_IMAGE)
    built = BuildArtifact(
        reference = "demo:latest",
        platform = "linux/arm64",
        digest = "sha256:" + "a" * 64,
        transport = ArtifactTransport.LOCAL_IMAGE,
        archive_path = None,
        created = True,
    )

    # Compare the artifact handoff.
    assert requirement.reference == built.reference
    assert built.created is True

    # Build a valid archive artifact.
    archive = BuildArtifact(
        reference = "demo:latest",
        platform = None,
        digest = None,
        transport = ArtifactTransport.DOCKER_ARCHIVE,
        archive_path = Path("/tmp/demo.tar"),
        created = False,
    )

    # Compare the archive path.
    assert archive.archive_path == Path("/tmp/demo.tar")

    # Reject blank references, platforms, and digests.
    with pytest.raises(ValueError):
        ArtifactRequirement(reference = "", platform = None, transport = ArtifactTransport.LOCAL_IMAGE)

    with pytest.raises(ValueError):
        ArtifactRequirement(reference = "demo", platform = " ", transport = ArtifactTransport.LOCAL_IMAGE)

    with pytest.raises(ValueError):
        BuildArtifact(reference = "demo", platform = None, digest = "", transport = ArtifactTransport.LOCAL_IMAGE, archive_path = None, created = False)

    # Reject a transport outside the neutral enum.
    with pytest.raises(ValueError):
        ArtifactRequirement(reference = "demo", platform = None, transport = "local-image")  # pyright: ignore[reportArgumentType]

    # Require an archive path for an archive transport.
    with pytest.raises(ValueError):
        BuildArtifact(reference = "demo", platform = None, digest = None, transport = ArtifactTransport.DOCKER_ARCHIVE, archive_path = None, created = False)

    # Forbid an archive path for a local image transport.
    with pytest.raises(ValueError):
        BuildArtifact(reference = "demo", platform = None, digest = None, transport = ArtifactTransport.LOCAL_IMAGE, archive_path = Path("/tmp/demo.tar"), created = False)

    # Reject a non-Boolean creation flag.
    with pytest.raises(ValueError):
        BuildArtifact(reference = "demo", platform = None, digest = None, transport = ArtifactTransport.LOCAL_IMAGE, archive_path = None, created = 1)  # pyright: ignore[reportArgumentType]


# Verify observations distinguish unavailable facts from reported-empty collections.
def test_observation_distinguishes_unavailable_from_empty_facts() -> None:
    # Build observations whose collections are unavailable and empty.
    unavailable = BoxObservation(name = "demo", state = BoxState.RUNNING, provenance = Provenance(catalogue = None, recipe = None), mounts = None, networks = None)
    empty = BoxObservation(name = "demo", state = BoxState.RUNNING, provenance = Provenance(catalogue = None, recipe = None), mounts = (), networks = ())

    # Compare the two meanings.
    assert unavailable.mounts is None
    assert unavailable.networks is None
    assert empty.mounts == ()
    assert empty.networks == ()


# Verify registry-facing values enforce identity and immutable binding collections.
def test_registry_values_enforce_their_invariants() -> None:
    # Build a valid catalogue registration with one binding.
    binding = CatalogueBinding(alias = "api_key", path = Path("/keys/api_key"))
    registration = CatalogueRegistration(name = "default", type = "local", path = Path("/home/catalogues/default"), bindings = (binding,))

    # Compare the registration facts.
    assert registration.bindings == (binding,)

    # Reject blank identities, invalid paths, and mutable bindings.
    with pytest.raises(ValueError):
        CatalogueRegistration(name = "", type = "local", path = Path("/home/catalogues/default"))

    with pytest.raises(ValueError):
        CatalogueRegistration(name = "default", type = " ", path = Path("/home/catalogues/default"))

    with pytest.raises(ValueError):
        CatalogueBinding(alias = "keys/api_key", path = Path("/keys/api_key"))

    with pytest.raises(ValueError):
        CatalogueRegistration(
            name = "default",
            type = "local",
            path = Path("/home/catalogues/default"),
            bindings = [binding],  # pyright: ignore[reportArgumentType]
        )

    # Reject duplicate binding aliases.
    with pytest.raises(ValueError):
        CatalogueRegistration(name = "default", type = "local", path = Path("/home/catalogues/default"), bindings = (binding, binding))

    # Build a secret binding and removal plan.
    secret = SecretBinding(catalogue = "default", alias = "api_key", host_path = Path("/keys/api_key"))
    removal = CatalogueRemovalPlan(home = Path("/home"), registration = registration)

    # Compare the binding and plan facts.
    assert secret.alias == "api_key"
    assert removal.registration is registration

    # Reject blank catalogue names, invalid aliases, and non-registration plans.
    with pytest.raises(ValueError):
        SecretBinding(catalogue = "", alias = "api_key", host_path = Path("/keys/api_key"))

    with pytest.raises(ValueError):
        SecretBinding(catalogue = "default", alias = "..", host_path = Path("/keys/api_key"))

    with pytest.raises(ValueError):
        CatalogueRemovalPlan(home = Path("/home"), registration = "default")  # pyright: ignore[reportArgumentType]

    # Require immutable registry values.
    with pytest.raises(dataclasses.FrozenInstanceError):
        registration.name = "other"  # pyright: ignore[reportAttributeAccessIssue]


# Verify volume declarations enforce physical identity and the shared scope.
def test_volume_declaration_enforces_physical_identity_and_shared_scope() -> None:
    # Accept a Docker-compatible case-sensitive physical name.
    declaration = VolumeDeclaration(name = "STATE.State-1", scope = "shared", target = "/home/example/.state")
    assert declaration.name == "STATE.State-1"

    # Reject project aliases, leading underscores, and host paths.
    for name in ("r", "_state", "host/state"):
        with pytest.raises(ValueError):
            VolumeDeclaration(name = name, scope = "shared", target = "/state")

    # Reject an unsupported scope and a relative or interpolated target.
    with pytest.raises(ValueError):
        VolumeDeclaration(name = "shared-state", scope = "private", target = "/state")

    for target in ("state", "../state", "/state/${USER}"):
        with pytest.raises(ValueError):
            VolumeDeclaration(name = "shared-state", scope = "shared", target = target)


# Verify observed volumes distinguish unavailable references from reported-empty ones.
def test_volume_info_distinguishes_unavailable_references() -> None:
    # Build a volume whose references are unavailable and one whose references are empty.
    unavailable = VolumeInfo(name = "state", driver = "local", mountpoint = None, in_use_by = None)
    empty = VolumeInfo(name = "state", driver = "local", mountpoint = None, in_use_by = ())
    assert unavailable.in_use_by is None
    assert empty.in_use_by == ()

    # Require an EnsuredVolume to wrap an observed volume and a Boolean creation flag.
    ensured = EnsuredVolume(info = empty, created = True)
    assert ensured.info is empty
    assert ensured.created is True

    with pytest.raises(ValueError):
        EnsuredVolume(info = "state", created = True)  # pyright: ignore[reportArgumentType]

    with pytest.raises(ValueError):
        EnsuredVolume(info = empty, created = 1)  # pyright: ignore[reportArgumentType]


# Verify observations reject absence and require the fixed workspace target.
def test_observation_requires_an_observed_state_and_fixed_workspace() -> None:
    # Require an observed state rather than a lookup result.
    with pytest.raises(ValueError):
        BoxObservation(name = "demo", state = BoxState.MISSING, provenance = Provenance(None, None))

    # Require a nonblank box identity.
    with pytest.raises(ValueError):
        BoxObservation(name = "", state = BoxState.RUNNING, provenance = Provenance(None, None))

    # Reject a workspace target that does not belong to the observed box.
    with pytest.raises(ValueError):
        BoxObservation(
            name = "demo",
            state = BoxState.RUNNING,
            provenance = Provenance(None, None),
            workspace = Workspace(host_directory = Path("/work/demo"), target = "/projects/other"),
        )

    # Accept the fixed target for the observed box name.
    observation_value = BoxObservation(
        name = "demo",
        state = BoxState.RUNNING,
        provenance = Provenance(None, None),
        workspace = Workspace(host_directory = Path("/work/demo"), target = "/projects/demo"),
    )
    assert observation_value.workspace is not None
    assert observation_value.workspace.target == "/projects/demo"


# Verify observed mounts and networks keep their validated mapped values.
def test_mount_and_network_values_validate_observations() -> None:
    # Accept one bind mount and one network.
    observed_mount = Mount(kind = "bind", source = "/work/demo", target = "/projects/demo")
    observed_network = Network(name = "demo_default", ip_address = "172.18.0.2")
    assert observed_mount.kind == "bind"
    assert observed_network.ip_address == "172.18.0.2"

    # Reject an unmodelled mount kind and a relative guest target.
    with pytest.raises(ValueError):
        Mount(kind = "tmpfs", source = "state", target = "/data")  # pyright: ignore[reportArgumentType]

    with pytest.raises(ValueError):
        Mount(kind = "volume", source = "state", target = "data")

    # Reject a blank network name or a non-string address.
    with pytest.raises(ValueError):
        Network(name = "", ip_address = "")

    with pytest.raises(ValueError):
        Network(name = "demo_default", ip_address = 1)  # pyright: ignore[reportArgumentType]


# Verify plans reject duplicate volume names and guest targets.
def test_plan_rejects_duplicate_volumes() -> None:
    # Build the fixed project and workspace values.
    project = Project(name = "demo", directory = Path("/work/demo"))
    workspace = Workspace(host_directory = Path("/work/demo"), target = "/projects/demo")

    # Reject two declarations with the same physical volume name.
    with pytest.raises(ValueError):
        SandboxPlan(
            project = project,
            workspace = workspace,
            volumes = (
                VolumeDeclaration(name = "shared", scope = "shared", target = "/state"),
                VolumeDeclaration(name = "shared", scope = "shared", target = "/cache"),
            ),
            secrets = (),
            allow_root = False,
        )

    # Reject two declarations mounted at the same guest target.
    with pytest.raises(ValueError):
        SandboxPlan(
            project = project,
            workspace = workspace,
            volumes = (
                VolumeDeclaration(name = "state", scope = "shared", target = "/data"),
                VolumeDeclaration(name = "cache", scope = "shared", target = "/data"),
            ),
            secrets = (),
            allow_root = False,
        )


# Verify removal plans preserve name-only display references.
def test_removal_plan_keeps_display_references() -> None:
    # Build a removal preview with one container and one network.
    removal = RemovalPlan(
        box = "demo",
        containers = (RuntimeRef(id = "abc", name = "demo-workspace-1"),),
        networks = (RuntimeRef(id = "net", name = "demo_default"),),
    )

    # Compare the preview identities.
    assert removal.containers[0].id == "abc"
    assert removal.networks[0].name == "demo_default"

    # Reject a removal preview without a box name.
    with pytest.raises(ValueError):
        RemovalPlan(box = "", containers = (), networks = ())
