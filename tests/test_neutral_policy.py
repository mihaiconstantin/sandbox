"""Verify neutral policy validates specs, mounts, secret deliveries, and initialization."""

# Imports.
import dataclasses
from pathlib import Path

# Import pytest for error assertions.
import pytest

# Import neutral domain values.
from sandbox.domain import MountSpec, Secret

# Import the policy modules.
from sandbox.policy.initialization import validate_initialization
from sandbox.policy.mounts import secret_deliveries
from sandbox.policy.spec import validate_spec

# Import the neutral fixtures.
from neutral_fixtures import CATALOGUE_ROOT, make_initialization, make_plan, make_spec, make_volume, volume_mount, workspace_mount


# Build a plan with one declared volume.
def volume_plan():
    # Build the plan and its declaration.
    declaration = make_volume()
    return make_plan(volumes = (declaration,)), declaration


# Verify a complete effective spec passes neutral policy.
def test_valid_spec_passes() -> None:
    # Validate the default spec and the catalogue root.
    plan = make_plan()
    validate_spec(plan, make_spec(plan), catalogue_root = CATALOGUE_ROOT)


# Verify the working directory must be the fixed workspace target.
def test_working_directory_must_be_the_workspace_target() -> None:
    # Reject an absent working directory.
    plan = make_plan()
    with pytest.raises(Exception) as absent:
        validate_spec(plan, dataclasses.replace(make_spec(plan), working_directory = None), catalogue_root = CATALOGUE_ROOT)
    assert getattr(absent.value, "field", None) == "working_directory"

    # Reject a different working directory.
    with pytest.raises(Exception) as wrong:
        validate_spec(plan, make_spec(plan, working_directory = "/"), catalogue_root = CATALOGUE_ROOT)
    assert getattr(wrong.value, "field", None) == "working_directory"


# Verify privileged and host-networked sandboxes are rejected.
def test_privileged_and_host_network_are_rejected() -> None:
    # Reject privileged mode.
    plan = make_plan()
    with pytest.raises(Exception) as privileged:
        validate_spec(plan, make_spec(plan, privileged = True), catalogue_root = CATALOGUE_ROOT)
    assert getattr(privileged.value, "field", None) == "privileged"

    # Reject host networking.
    with pytest.raises(Exception) as network:
        validate_spec(plan, make_spec(plan, host_network = True), catalogue_root = CATALOGUE_ROOT)
    assert getattr(network.value, "field", None) == "host_network"


# Verify explicit root execution requires the recipe root policy.
@pytest.mark.parametrize("user", ["root", "root:root", 0, "0", "0:0"])
def test_explicit_root_user_requires_allow_root(user: str | int) -> None:
    # Reject root without the recipe permission.
    plan = make_plan()
    with pytest.raises(Exception) as error:
        validate_spec(plan, make_spec(plan, user = user), catalogue_root = CATALOGUE_ROOT)
    assert type(error.value).__name__ == "RootExecutionNotAllowed"

    # Permit root when the recipe allows it.
    permitted = make_plan(allow_root = True)
    validate_spec(permitted, make_spec(permitted, user = user), catalogue_root = CATALOGUE_ROOT)


# Verify non-root users and the image default pass root policy.
@pytest.mark.parametrize("user", [None, "app", "1000:1000", 1000])
def test_non_root_users_pass(user: str | int | None) -> None:
    # Validate the non-root user.
    plan = make_plan()
    validate_spec(plan, make_spec(plan, user = user), catalogue_root = CATALOGUE_ROOT)


# Verify every bind source stays inside the project or catalogue directory.
def test_bind_sources_must_stay_inside_the_project_or_catalogue() -> None:
    # Permit a contained catalogue asset.
    plan = make_plan()
    contained = MountSpec(kind = "bind", source = CATALOGUE_ROOT / "assets", target = "/opt/assets", read_only = True)
    validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), contained)), catalogue_root = CATALOGUE_ROOT)

    # Reject a bind source outside both roots.
    outside = MountSpec(kind = "bind", source = Path("/etc"), target = "/host-etc", read_only = True)
    with pytest.raises(Exception) as error:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), outside)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(error.value, "field", "").startswith("mounts")

    # Reject catalogue content without a declared catalogue root.
    with pytest.raises(Exception):
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), contained)))


# Verify the Docker socket cannot be mounted.
def test_docker_socket_mounts_are_rejected() -> None:
    # Build a contained socket source, which policy still rejects by name.
    plan = make_plan()
    socket = MountSpec(kind = "bind", source = plan.project.directory / "docker.sock", target = "/var/run/docker.sock", read_only = True)
    with pytest.raises(Exception) as error:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), socket)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(error.value, "field", "").startswith("mounts")


# Verify mount targets cannot repeat.
def test_mount_targets_must_be_unique() -> None:
    # Duplicate the workspace target with a second bind.
    plan = make_plan()
    first = workspace_mount(plan)
    second = MountSpec(kind = "bind", source = plan.project.directory, target = plan.workspace.target, read_only = True)
    with pytest.raises(Exception) as error:
        validate_spec(plan, make_spec(plan, mounts = (first, second)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(error.value, "field", "").startswith("mounts")


# Verify the workspace bind is required exactly once at the fixed target.
def test_workspace_bind_is_required_exactly_once() -> None:
    # Reject a spec without the project bind.
    plan = make_plan()
    with pytest.raises(Exception) as missing:
        validate_spec(plan, make_spec(plan, mounts = ()), catalogue_root = CATALOGUE_ROOT)
    assert getattr(missing.value, "field", "").startswith("mounts")

    # Reject a project bind with the wrong host source.
    wrong_source = MountSpec(kind = "bind", source = CATALOGUE_ROOT, target = plan.workspace.target, read_only = False)
    with pytest.raises(Exception) as wrong:
        validate_spec(plan, make_spec(plan, mounts = (wrong_source,)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(wrong.value, "field", "").startswith("mounts")

    # Reject a named volume at the workspace target.
    named = MountSpec(kind = "volume", source = "cache", target = plan.workspace.target, read_only = False)
    with pytest.raises(Exception):
        validate_spec(plan, make_spec(plan, mounts = (named,)), catalogue_root = CATALOGUE_ROOT)


# Verify declared volumes must be mounted writable at their declared targets.
def test_declared_volumes_must_match_their_mounts() -> None:
    # Reject a missing volume mount.
    plan, declaration = volume_plan()
    with pytest.raises(Exception) as missing:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan),)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(missing.value, "field", None) == "volumes"

    # Reject a read-only declared volume.
    with pytest.raises(Exception) as read_only:
        validate_spec(
            plan,
            make_spec(plan, mounts = (workspace_mount(plan), volume_mount(declaration, read_only = True))),
            catalogue_root = CATALOGUE_ROOT,
        )
    assert getattr(read_only.value, "field", None) == "volumes"

    # Reject a declared volume mounted at another target.
    wrong = MountSpec(kind = "volume", source = declaration.name, target = "/var/cache/other", read_only = False)
    with pytest.raises(Exception) as target:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), wrong)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(target.value, "field", None) == "volumes"


# Verify undeclared named volumes cannot be mounted.
def test_undeclared_volume_mounts_are_rejected() -> None:
    # Mount a physical volume the plan never declares.
    plan = make_plan()
    undeclared = MountSpec(kind = "volume", source = "unmanaged", target = "/var/cache/unmanaged", read_only = False)
    with pytest.raises(Exception) as error:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), undeclared)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(error.value, "field", None) == "volumes"


# Verify secret files are delivered separately from recipe mounts.
def test_secret_deliveries_are_derived_separately_from_recipe_mounts() -> None:
    # Build a plan with one bound secret.
    secret = Secret(alias = "api_key", host_path = Path("/work/secrets/api_key"))
    plan = make_plan(secrets = (secret,))

    # Derive the fixed read-only delivery.
    deliveries = secret_deliveries(plan)
    assert deliveries == (MountSpec(kind = "bind", source = secret.host_path, target = "/run/secrets/api_key", read_only = True),)

    # The recipe mounts need not repeat the secret delivery.
    validate_spec(plan, make_spec(plan), catalogue_root = CATALOGUE_ROOT)


# Verify recipe mounts cannot claim or expose secret files.
def test_recipe_mounts_cannot_claim_or_expose_secret_files() -> None:
    # Build a plan with one bound secret.
    secret = Secret(alias = "api_key", host_path = Path("/work/secrets/api_key"))
    plan = make_plan(secrets = (secret,))

    # Reject a recipe mount at the secret delivery target.
    claimed = MountSpec(kind = "bind", source = plan.project.directory / "api_key", target = "/run/secrets/api_key", read_only = True)
    with pytest.raises(Exception) as target:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), claimed)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(target.value, "field", None) == "secrets"

    # Reject a writable recipe bind exposing the secret host file.
    exposed = MountSpec(kind = "bind", source = secret.host_path, target = "/opt/api_key", read_only = False)
    with pytest.raises(Exception) as source:
        validate_spec(plan, make_spec(plan, mounts = (workspace_mount(plan), exposed)), catalogue_root = CATALOGUE_ROOT)
    assert getattr(source.value, "field", None) == "secrets"


# Verify a valid initialization passes, including the volume-less path.
def test_initialization_accepts_non_root_and_declared_targets() -> None:
    # Accept a non-root initialization without volumes.
    plan = make_plan()
    validate_initialization(plan, make_initialization(uid = 1000))

    # Accept a non-root initialization on a declared volume target.
    plan, declaration = volume_plan()
    validate_initialization(plan, make_initialization(uid = 1000, targets = (declaration.target,)), mounts = make_spec(plan).mounts)


# Verify initialization targets must be declared volume targets.
def test_initialization_rejects_undeclared_targets() -> None:
    # Reject a target the plan does not declare.
    plan = make_plan()
    with pytest.raises(Exception) as error:
        validate_initialization(plan, make_initialization(uid = 1000, targets = ("/var/cache/unknown",)))
    assert getattr(error.value, "field", None) == "initialization.targets"


# Verify root UID is rejected on volume and volume-less creates unless allowed.
def test_initialization_root_policy_applies_to_every_create_path() -> None:
    # Reject UID 0 without volumes.
    plan = make_plan()
    with pytest.raises(Exception) as volume_less:
        validate_initialization(plan, make_initialization(uid = 0))
    assert type(volume_less.value).__name__ == "RootExecutionNotAllowed"

    # Reject UID 0 with a declared volume.
    volume_plan_instance, declaration = volume_plan()
    with pytest.raises(Exception) as volume:
        validate_initialization(volume_plan_instance, make_initialization(uid = 0, targets = (declaration.target,)))
    assert type(volume.value).__name__ == "RootExecutionNotAllowed"

    # Permit UID 0 when the recipe allows root.
    permitted = make_plan(allow_root = True)
    validate_initialization(permitted, make_initialization(uid = 0))


# Verify initialization targets must be installed writable.
def test_initialization_rejects_read_only_targets() -> None:
    # Build a declared volume mounted read-only.
    plan, declaration = volume_plan()
    mounts = (workspace_mount(plan), volume_mount(declaration, read_only = True))
    with pytest.raises(Exception) as error:
        validate_initialization(plan, make_initialization(uid = 1000, targets = (declaration.target,)), mounts = mounts)
    assert getattr(error.value, "field", None) == "initialization.targets"
