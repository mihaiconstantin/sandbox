"""Build neutral plans, definitions, specs, and initializations for focused tests."""

# Imports.
from pathlib import Path

# Import neutral domain values.
from sandbox.domain import (
    Initialization,
    MountSpec,
    Project,
    RecipeDefinition,
    SandboxPlan,
    SandboxSpec,
    Secret,
    VolumeDeclaration,
    Workspace,
)

# Declare the fixed host directories used by the neutral fixtures.
PROJECT_DIR: Path = Path("/work/demo")
CATALOGUE_ROOT: Path = Path("/catalogues/default")


# Build a plan whose workspace binds the project at the fixed target.
def make_plan(
    *,
    name: str = "demo",
    directory: Path = PROJECT_DIR,
    volumes: tuple[VolumeDeclaration, ...] = (),
    secrets: tuple[Secret, ...] = (),
    allow_root: bool = False,
) -> SandboxPlan:
    # Build the neutral plan.
    return SandboxPlan(
        project = Project(name = name, directory = directory),
        workspace = Workspace(host_directory = directory, target = f"/projects/{name}"),
        volumes = volumes,
        secrets = secrets,
        allow_root = allow_root,
    )


# Build an opaque recipe definition for the fixture catalogue.
def make_definition(service: str = "workspace", recipe: str = "base") -> RecipeDefinition:
    # Build the parent-first source chain.
    return RecipeDefinition(
        catalogue = "default",
        recipe = recipe,
        catalogue_root = CATALOGUE_ROOT,
        files = (CATALOGUE_ROOT / "compose.yaml",),
        service = service,
    )


# Build a declared shared volume.
def make_volume(name: str = "cache", target: str = "/var/cache/demo") -> VolumeDeclaration:
    # Build the volume declaration.
    return VolumeDeclaration(name = name, scope = "shared", target = target)


# Build the observed workspace bind for a plan.
def workspace_mount(plan: SandboxPlan) -> MountSpec:
    # Bind the host project directory at the fixed guest target.
    return MountSpec(kind = "bind", source = plan.project.directory, target = plan.workspace.target, read_only = False)


# Build the observed mount for a declared volume.
def volume_mount(declaration: VolumeDeclaration, *, read_only: bool = False) -> MountSpec:
    # Mount the physical volume at its declared target.
    return MountSpec(kind = "volume", source = declaration.name, target = declaration.target, read_only = read_only)


# Build a valid effective sandbox spec for a plan.
def make_spec(
    plan: SandboxPlan,
    *,
    image: str = "sandbox/demo:latest",
    platform: str | None = None,
    user: str | int | None = None,
    working_directory: str | None = None,
    privileged: bool = False,
    host_network: bool = False,
    mounts: tuple[MountSpec, ...] | None = None,
) -> SandboxSpec:
    # Derive the default mounts from the plan and its declarations.
    effective_mounts: tuple[MountSpec, ...] = (
        (workspace_mount(plan), *(volume_mount(declaration) for declaration in plan.volumes))
        if mounts is None
        else mounts
    )

    # Build the sandbox spec with the workspace target as the default working directory.
    return SandboxSpec(
        image = image,
        platform = platform,
        user = user,
        working_directory = plan.workspace.target if working_directory is None else working_directory,
        privileged = privileged,
        host_network = host_network,
        mounts = effective_mounts,
    )


# Build an initialization for an effective UID and declared targets.
def make_initialization(uid: int = 1000, targets: tuple[str, ...] = ()) -> Initialization:
    # Build the neutral initialization.
    return Initialization(uid = uid, targets = targets)
