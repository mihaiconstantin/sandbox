# Imports.
import ast
import dataclasses
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType

import pytest

# Import the public error root and structured command failure facts.
from sandbox.errors.base import CommandFailure, InputError, SandboxError


# Verify the root accepts the neutral family.
def test_sandbox_error_is_the_public_root() -> None:
    # Build the root error.
    error: SandboxError = SandboxError("failure")

    # Compare the root family and rendering.
    assert isinstance(error, Exception)
    assert str(error) == "failure"


# Verify input errors keep the documented builtin compatibility base.
def test_input_error_is_a_value_error() -> None:
    # Compare the direct bases.
    assert InputError.__bases__ == (SandboxError, ValueError)


# Verify a command failure is a frozen structured value.
def test_command_failure_is_a_frozen_value() -> None:
    # Build the failure facts.
    failure: CommandFailure = CommandFailure(
        backend = "docker",
        operation = "build",
        command = ("docker", "build", "."),
        exit_code = 17,
        diagnostic = "context failed",
        timed_out = False,
    )

    # Compare the value shape.
    assert dataclasses.is_dataclass(failure)
    assert failure.backend == "docker"
    assert failure.operation == "build"
    assert failure.command == ("docker", "build", ".")
    assert failure.exit_code == 17
    assert failure.diagnostic == "context failed"
    assert failure.timed_out is False

    # Require immutability.
    with pytest.raises(FrozenInstanceError):
        setattr(failure, "exit_code", 1)


# Verify the optional command and timeout facts have explicit defaults.
def test_command_failure_defaults() -> None:
    # Build a failure without a command.
    failure: CommandFailure = CommandFailure(
        backend = "runtime",
        operation = "create",
        command = None,
        exit_code = 1,
        diagnostic = "",
    )

    # Compare the defaulted facts.
    assert failure.command is None
    assert failure.timed_out is False


# Verify configuration errors keep their field facts and prefix behavior.
def test_configuration_error_facts() -> None:
    # Import the configuration family.
    from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed

    # Build a field error.
    error: ConfigurationError = ConfigurationError("catalogues.work", "Must be a mapping.")

    # Compare the input compatibility and facts.
    assert isinstance(error, InputError)
    assert isinstance(error, ValueError)
    assert (error.field, error.message) == ("catalogues.work", "Must be a mapping.")

    # Apply a prefix without changing the original error.
    prefixed: ConfigurationError = error.with_prefix("catalogues")

    # Compare the prefixed facts.
    assert (prefixed.field, prefixed.message) == ("catalogues.catalogues.work", "Must be a mapping.")
    assert error.field == "catalogues.work"

    # Compare the root policy facts.
    root: RootExecutionNotAllowed = RootExecutionNotAllowed(uid = 0, source = "image-default", image = "base:latest")
    assert isinstance(root, ConfigurationError)
    assert (root.uid, root.source, root.image) == (0, "image-default", "base:latest")


# Verify recipe errors remain input errors with neutral facts.
def test_recipe_error_facts() -> None:
    # Import the recipe family.
    from sandbox.errors.recipes import RecipeError, RecipeUnresolved

    # Build an unresolved recipe.
    error: RecipeUnresolved = RecipeUnresolved("services.demo.image", "Must be an inspectable image.")

    # Compare the input compatibility and facts.
    assert isinstance(error, RecipeError)
    assert isinstance(error, InputError)
    assert isinstance(error, ValueError)
    assert (error.field, error.message) == ("services.demo.image", "Must be an inspectable image.")


# Verify catalogue errors remain input errors with their message facts.
def test_catalogue_error_facts() -> None:
    # Import the catalogue family.
    from sandbox.errors.catalogues import CatalogueError, CatalogueInstallError, RegistryError

    # Build the catalogue failures.
    install: CatalogueInstallError = CatalogueInstallError("The catalogue source is not a directory.")
    registry: RegistryError = RegistryError("The catalogue registry is not a table.")

    # Compare the input compatibility and facts.
    for error in (install, registry):
        assert isinstance(error, CatalogueError)
        assert isinstance(error, InputError)
        assert isinstance(error, ValueError)
    assert install.message == "The catalogue source is not a directory."
    assert registry.message == "The catalogue registry is not a table."


# Verify secret errors remain input errors with their structured facts.
def test_secret_error_facts(tmp_path: Path) -> None:
    # Import the secret family.
    from sandbox.errors.secrets import MissingSecret, SecretError, SecretFileError

    # Build a missing secret.
    missing: MissingSecret = MissingSecret("tools", "token", "demo")

    # Compare the input compatibility and facts.
    assert isinstance(missing, SecretError)
    assert isinstance(missing, InputError)
    assert isinstance(missing, ValueError)
    assert (missing.catalogue, missing.alias, missing.recipe) == ("tools", "token", "demo")

    # Build an unusable secret file.
    path = tmp_path / "token"
    secret_file: SecretFileError = SecretFileError(path, "does not exist or is not a regular file")

    # Compare the input compatibility and facts.
    assert isinstance(secret_file, SecretError)
    assert isinstance(secret_file, ValueError)
    assert (secret_file.path, secret_file.reason) == (path, "does not exist or is not a regular file")


# Verify box lookup and state errors keep their domain categories and labels.
def test_box_error_facts() -> None:
    # Import the box family.
    from sandbox.errors.boxes import (
        BoxAmbiguous,
        BoxLookupError,
        BoxNotFound,
        BoxNotReady,
        BoxNotRunning,
        BoxStateError,
    )

    # Build the lookup failures.
    missing: BoxNotFound = BoxNotFound("demo", backend = "docker")
    ambiguous: BoxAmbiguous = BoxAmbiguous("demo", 2, backend = "microsandbox")

    # Compare the lookup facts and optional backend labels.
    for error in (missing, ambiguous):
        assert isinstance(error, BoxLookupError)
        assert isinstance(error, SandboxError)
        assert not isinstance(error, InputError)
        assert not hasattr(error, "box_noun")
    assert (missing.name, missing.backend) == ("demo", "docker")
    assert (ambiguous.name, ambiguous.count, ambiguous.backend) == ("demo", 2, "microsandbox")

    # Compare the state facts.
    state: BoxStateError = BoxStateError("demo", state = "created", detail = "Creation has not completed.")
    assert isinstance(state, SandboxError)
    assert (state.name, state.state, state.detail) == ("demo", "created", "Creation has not completed.")

    # Require the named state subclasses.
    assert isinstance(BoxNotReady("demo"), BoxStateError)
    assert isinstance(BoxNotRunning("demo"), BoxStateError)


# Verify ownership errors stand alone from removal errors.
def test_ownership_error_facts() -> None:
    # Import the ownership and removal families.
    from sandbox.errors.ownership import OwnershipViolation
    from sandbox.errors.removal import RemovalError

    # Build an ownership failure.
    error: OwnershipViolation = OwnershipViolation("container", "abc")

    # Compare the facts and the absence of the retired hybrid.
    assert isinstance(error, SandboxError)
    assert not isinstance(error, RemovalError)
    assert (error.resource_kind, error.identifier) == ("container", "abc")


# Verify volume errors keep their facts without the retired multiple inheritance.
def test_volume_error_facts() -> None:
    # Import the volume family.
    from sandbox.errors.base import CommandFailure
    from sandbox.errors.engine import EngineFailure
    from sandbox.errors.ownership import OwnershipViolation
    from sandbox.errors.removal import RemovalError
    from sandbox.errors.volumes import (
        VolumeCreateFailed,
        VolumeError,
        VolumeInUse,
        VolumeNotFound,
        VolumeOwnershipError,
        VolumeReferencesUnavailable,
    )

    # Build the volume failures.
    missing: VolumeNotFound = VolumeNotFound("state")
    in_use: VolumeInUse = VolumeInUse("state", backend = "docker")
    unavailable: VolumeReferencesUnavailable = VolumeReferencesUnavailable("state")
    failure: CommandFailure = CommandFailure("docker", "volume.create", ("docker", "volume", "create", "state"), 1, "denied")
    create_failed: VolumeCreateFailed = VolumeCreateFailed("state", failure)
    ownership: VolumeOwnershipError = VolumeOwnershipError("state")

    # Compare the volume category and facts.
    for error in (missing, in_use, unavailable, create_failed):
        assert isinstance(error, VolumeError)
        assert isinstance(error, SandboxError)
    assert missing.name == "state"
    assert (in_use.name, in_use.backend) == ("state", "docker")
    assert unavailable.name == "state"
    assert (create_failed.name, create_failed.failure) == ("state", failure)
    assert not isinstance(create_failed, EngineFailure)

    # Compare the ownership category without the retired hybrid.
    assert isinstance(ownership, OwnershipViolation)
    assert not isinstance(ownership, RemovalError)
    assert (ownership.resource_kind, ownership.identifier) == ("volume", "state")


# Verify removal errors keep their facts and builtin compatibility base.
def test_removal_error_facts() -> None:
    # Import the removal family.
    from sandbox.errors.boxes import BoxLookupError
    from sandbox.errors.removal import IncompleteRemoval, NetworkInUse, NothingToRemove, RemovalError

    # Build the removal failures.
    empty: NothingToRemove = NothingToRemove("demo")
    network: NetworkInUse = NetworkInUse("demo_default", backend = "docker")
    incomplete: IncompleteRemoval = IncompleteRemoval("box", "demo", detail = "A container remains.", backend = "docker")

    # Compare the removal category and retired hybrid.
    assert isinstance(empty, RemovalError)
    assert not isinstance(empty, BoxLookupError)
    assert empty.name == "demo"
    assert (network.name, network.backend) == ("demo_default", "docker")

    # Compare the incomplete-removal builtin compatibility and facts.
    assert IncompleteRemoval.__bases__ == (RemovalError, RuntimeError)
    assert isinstance(incomplete, RuntimeError)
    assert (incomplete.resource_kind, incomplete.identifier) == ("box", "demo")
    assert (incomplete.detail, incomplete.backend) == ("A container remains.", "docker")


# Verify engine failures hold structured facts without a second domain parent.
def test_engine_error_facts() -> None:
    # Import the engine family.
    from sandbox.errors.engine import EngineError, EngineFailure, EngineOutputInvalid

    # Build the command failure and engine error.
    failure: CommandFailure = CommandFailure("docker", "start", ("docker", "start", "abc"), 125, "conflict")
    error: EngineFailure = EngineFailure(failure)

    # Compare the category and facts.
    assert isinstance(error, EngineError)
    assert isinstance(error, SandboxError)
    assert error.failure is failure

    # Build invalid output with an oversized sample.
    invalid: EngineOutputInvalid = EngineOutputInvalid("docker", "resolve", "x" * 300)

    # Compare the category and bounded facts.
    assert isinstance(invalid, EngineError)
    assert (invalid.backend, invalid.operation) == ("docker", "resolve")
    assert invalid.sample == "x" * 200


# Verify build failures keep their category and command facts.
def test_build_error_facts() -> None:
    # Import the build and engine families.
    from sandbox.errors.build import BuildError, BuildFailed
    from sandbox.errors.engine import EngineError

    # Build the command failure and build error.
    failure: CommandFailure = CommandFailure("docker", "build", ("docker", "build", "."), 17, "context failed")
    error: BuildFailed = BuildFailed(failure)

    # Compare the category and facts.
    assert isinstance(error, BuildError)
    assert isinstance(error, SandboxError)
    assert not isinstance(error, EngineError)
    assert error.failure is failure


# Verify create failures keep their categories, facts, and backend label.
def test_create_error_facts() -> None:
    # Import the create and engine families.
    from sandbox.errors.create import CreateError, CreateFailed, CreatePostconditionFailed
    from sandbox.errors.engine import EngineError

    # Build the command failure and create error.
    failure: CommandFailure = CommandFailure("docker", "create", ("docker", "compose", "up"), 1, "denied")
    error: CreateFailed = CreateFailed(failure)
    postcondition: CreatePostconditionFailed = CreatePostconditionFailed("demo", backend = "microsandbox")

    # Compare the create categories and facts.
    assert isinstance(error, CreateError)
    assert isinstance(postcondition, CreateError)
    assert isinstance(error, SandboxError)
    assert not isinstance(error, EngineError)
    assert error.failure is failure
    assert (postcondition.name, postcondition.backend) == ("demo", "microsandbox")
    assert not hasattr(postcondition, "box_noun")


# Verify prerequisite errors keep their tool and version facts.
def test_prerequisite_error_facts() -> None:
    # Import the prerequisite family.
    from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

    # Compare the documented kinds.
    assert issubclass(PrerequisiteKind, str)
    assert (PrerequisiteKind.MISSING.value, PrerequisiteKind.UNUSABLE.value, PrerequisiteKind.VERSION.value) == (
        "missing",
        "unusable",
        "version",
    )

    # Build a version prerequisite error.
    error: PrerequisiteError = PrerequisiteError(
        "docker compose",
        PrerequisiteKind.VERSION,
        requirement = ">= 5.6.0",
        found = "5.5.0",
        operation = "runtime.prepare",
        diagnostic = "version is too old",
        hint = "Upgrade the Compose plugin.",
    )

    # Compare the category and facts.
    assert isinstance(error, SandboxError)
    assert not isinstance(error, InputError)
    assert error.tool == "docker compose"
    assert error.kind is PrerequisiteKind.VERSION
    assert (error.requirement, error.found) == (">= 5.6.0", "5.5.0")
    assert (error.operation, error.diagnostic, error.hint) == ("runtime.prepare", "version is too old", "Upgrade the Compose plugin.")

    # Compare the optional fact defaults.
    missing: PrerequisiteError = PrerequisiteError("git", PrerequisiteKind.MISSING)
    assert (missing.requirement, missing.found, missing.operation) == (None, None, None)
    assert (missing.diagnostic, missing.hint) == ("", None)


# Verify capability errors keep their runtime feature facts.
def test_capability_error_facts() -> None:
    # Import the capability and engine families.
    from sandbox.errors.capabilities import ArtifactRejected, CapabilityError, UnsupportedFeature, UnsupportedOperation
    from sandbox.errors.engine import EngineError

    # Build the capability failures.
    feature: UnsupportedFeature = UnsupportedFeature("native-secret-file", detail = "Use an archive.", backend = "runtime")
    operation: UnsupportedOperation = UnsupportedOperation("attach", backend = "runtime")
    artifact: ArtifactRejected = ArtifactRejected(
        "oci-archive",
        reference = "example:latest",
        expected_platform = "linux/arm64",
        actual_platform = "linux/amd64",
        detail = "Transport mismatch.",
    )

    # Compare the capability categories and facts.
    assert isinstance(feature, CapabilityError)
    assert isinstance(operation, UnsupportedFeature)
    assert not isinstance(operation, EngineError)
    assert isinstance(artifact, CapabilityError)
    assert (feature.feature, feature.detail, feature.backend) == ("native-secret-file", "Use an archive.", "runtime")
    assert (operation.operation, operation.backend) == ("attach", "runtime")
    assert (artifact.transport, artifact.reference) == ("oci-archive", "example:latest")
    assert (artifact.expected_platform, artifact.actual_platform) == ("linux/arm64", "linux/amd64")


# Verify the terminal error carries only an optional backend label.
def test_terminal_error_facts() -> None:
    # Import the terminal family.
    from sandbox.errors.terminal import InteractiveTerminalRequired, TerminalError

    # Build the terminal failure.
    error: InteractiveTerminalRequired = InteractiveTerminalRequired(backend = "docker")

    # Compare the category and facts.
    assert isinstance(error, TerminalError)
    assert isinstance(error, SandboxError)
    assert error.backend == "docker"
    assert not hasattr(error, "box_noun")


# Declare the new error modules that make up the final family.
ERROR_MODULE_NAMES: tuple[str, ...] = (
    "base",
    "configuration",
    "recipes",
    "catalogues",
    "secrets",
    "boxes",
    "ownership",
    "volumes",
    "removal",
    "engine",
    "build",
    "create",
    "prerequisites",
    "capabilities",
    "terminal",
)

# Declare the adapter and CLI vocabulary forbidden in new public definitions.
FORBIDDEN_VOCABULARY: tuple[str, ...] = ("docker", "compose", "click", "rich", "podman", "microsandbox")


# Import one new error module by name.
def import_error_module(name: str) -> ModuleType:
    # Import the module lazily so the test file can name every module.
    import importlib

    return importlib.import_module(f"sandbox.errors.{name}")


# Yield every error class defined by a new error module.
def defined_error_classes() -> list[type[SandboxError]]:
    # Import the root for the subclass check.
    from sandbox.errors.base import SandboxError

    # Collect the classes in declaration order.
    classes: list[type[SandboxError]] = []
    for name in ERROR_MODULE_NAMES:
        module = import_error_module(name)
        for value in vars(module).values():
            candidate: object = value
            if isinstance(candidate, type) and issubclass(candidate, SandboxError) and candidate.__module__ == module.__name__:
                classes.append(candidate)

    # Return the collected classes.
    return classes


# Verify every new class belongs to the public root and keeps one domain parent.
def test_new_family_has_one_root_and_no_domain_multiple_inheritance() -> None:
    # Import the builtin compatibility bases.
    from sandbox.errors.base import InputError, SandboxError
    from sandbox.errors.removal import IncompleteRemoval

    # Require every class to belong to the root.
    for error in defined_error_classes():
        assert issubclass(error, SandboxError)

    # Require the documented builtin bases to stay direct and unique.
    assert ValueError in InputError.__bases__
    assert RuntimeError in IncompleteRemoval.__bases__
    for error in defined_error_classes():
        # Count the error-family direct bases.
        domain_bases: list[type[object]] = [base for base in error.__bases__ if issubclass(base, SandboxError)]
        assert len(domain_bases) <= 1, error.__name__

        # Require every other class to avoid a direct builtin base.
        if error is not InputError:
            assert ValueError not in error.__bases__, error.__name__
        if error is not IncompleteRemoval:
            assert RuntimeError not in error.__bases__, error.__name__


# Verify the retired hybrid hierarchies stay retired.
def test_retired_error_hybrids_are_absent() -> None:
    # Import the new families.
    from sandbox.errors.boxes import BoxLookupError
    from sandbox.errors.build import BuildFailed
    from sandbox.errors.capabilities import UnsupportedOperation
    from sandbox.errors.create import CreateFailed
    from sandbox.errors.engine import EngineError
    from sandbox.errors.removal import IncompleteRemoval, NothingToRemove, RemovalError
    from sandbox.errors.volumes import VolumeCreateFailed, VolumeOwnershipError

    # Require the documented category-only hierarchies.
    assert not issubclass(NothingToRemove, BoxLookupError)
    assert not issubclass(VolumeOwnershipError, RemovalError)
    assert not issubclass(VolumeCreateFailed, EngineError)
    assert not issubclass(BuildFailed, EngineError)
    assert not issubclass(CreateFailed, EngineError)
    assert not issubclass(UnsupportedOperation, EngineError)
    assert issubclass(IncompleteRemoval, RuntimeError)


# Verify new definitions contain no adapter nouns or CLI text.
def test_new_definitions_have_no_backend_or_cli_vocabulary() -> None:
    # Import the error package location.
    import sandbox.errors as errors_package

    # Check each new module source.
    for name in ERROR_MODULE_NAMES:
        path = Path(errors_package.__file__).parent / f"{name}.py"
        source: str = path.read_text(encoding = "utf-8")
        lowered: str = source.lower()
        for word in FORBIDDEN_VOCABULARY:
            assert word not in lowered, f"{path.name} contains {word!r}"

    # Require the removed noun field to stay absent.
    for error in defined_error_classes():
        assert "box_noun" not in vars(error), error.__name__


# Verify the new modules import only the standard library and the error package.
def test_new_error_modules_are_stdlib_only() -> None:
    # Import the error package location and the standard-library module names.
    import sandbox.errors as errors_package
    import sys

    # Check each module source.
    for path in sorted(Path(errors_package.__file__).parent.glob("*.py")):
        tree: ast.Module = ast.parse(path.read_text(encoding = "utf-8"))
        for node in ast.walk(tree):
            # Collect the imported module name.
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue

            # Require every import to be standard library or the error package.
            for imported in names:
                root: str = imported.split(".")[0]
                assert root in sys.stdlib_module_names or imported == "sandbox" or imported.startswith("sandbox.errors"), (
                    path.name,
                    imported,
                )


# Declare every non-class name the public initializer must export.
PUBLIC_NON_CLASSES: tuple[str, ...] = ("CommandFailure", "InputError", "PrerequisiteKind", "SandboxError")


# Verify the initializer exports the complete final family and nothing retired.
def test_initializer_exports_the_complete_final_family() -> None:
    # Import the package and the modules that define each class.
    import sandbox.errors as errors_package

    # Compare the declared and actual export surfaces.
    expected: set[str] = {error.__name__ for error in defined_error_classes()} | set(PUBLIC_NON_CLASSES)
    assert set(errors_package.__all__) == expected
    for name in expected:
        assert hasattr(errors_package, name), name

    # Require the initializer to re-export each defining module object.
    assert errors_package.SandboxError is SandboxError
    assert errors_package.CommandFailure.__module__ == "sandbox.errors.base"
    assert errors_package.InputError.__module__ == "sandbox.errors.base"
    assert errors_package.PrerequisiteKind.__module__ == "sandbox.errors.prerequisites"

    # Require the retired compatibility names to stay absent.
    for retired in ("IncompleteRemovalError", "box_noun", "Application"):
        assert not hasattr(errors_package, retired), retired


# Verify selected final behavior is unchanged through the package.
def test_public_behavior_through_the_package() -> None:
    # Import the final exports through the package.
    import sandbox.errors as errors_package

    # Compare the structured facts and configuration prefix behavior.
    error = errors_package.ConfigurationError("catalogues", "Must be a table.")
    assert error.with_prefix("home").field == "home.catalogues"
    assert errors_package.InputError.__bases__ == (errors_package.SandboxError, ValueError)
