# Imports.
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Import domain values.
from sandbox.domain import Initialization, RecipeDefinition, SandboxPlan
from sandbox.domain.paths import guest_target_key

# Import the typed input errors.
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.secrets import SecretFileError

# Import the Compose labels.
from sandbox.integrations.docker.compose.labels import (
    MANAGED_LABEL,
    PROJECT_LABEL,
    RESOURCE_LABEL,
    ROLE_LABEL,
)

# Import the projection values.
from sandbox.integrations.docker.compose.projection import (
    HookFacts,
    HooksFacts,
    Projection,
    ServiceFacts,
)

# Match the numeric ownership initializer argument.
_OWNER_ARGUMENT = re.compile(r"\+[0-9]+")


# Require the bound secret files to be readable regular files.
def validate_secret_files(plan: SandboxPlan) -> None:
    # Validate every bound secret file.
    for secret in plan.secrets:
        # Resolve the host file without requiring it to exist.
        path: Path = secret.host_path.expanduser()

        # If the secret source is not a regular file.
        if not path.is_file():
            # Throw the typed secret-file error.
            raise SecretFileError(secret.host_path, "Must reference an existing file.")

        # If the secret source cannot be read by the caller.
        if not os.access(path, os.R_OK):
            # Throw the typed secret-file error.
            raise SecretFileError(secret.host_path, "Must be readable.")


# Refuse an image healthcheck that the root initialization hook cannot disable.
def validate_image_healthcheck(inspection: Mapping[str, Any], service: str) -> None:
    # Read the service image field used by the guard.
    field: str = f"services.{service}.image"

    # Require the image configuration mapping.
    configuration: Any = inspection.get("Config")
    if not isinstance(configuration, Mapping):
        # Throw.
        raise RecipeUnresolved(field, "Must be a mapping.")

    # Read the immutable image healthcheck.
    health: Any = configuration.get("Healthcheck")

    # If the image has no healthcheck, the initialization command is the only workload.
    if health is None:
        # Return without imposing application-health behavior on the hook.
        return

    # Require the healthcheck mapping.
    if not isinstance(health, Mapping):
        # Throw.
        raise RecipeUnresolved(field, "Must be a mapping.")

    # Read the image healthcheck test.
    test: Any = health.get("Test")

    # If image code would also execute inside the root hook, refuse the unsafe initialization.
    if test and test != ["NONE"]:
        # Throw the current user-facing configuration failure.
        raise RecipeUnresolved(field, "The image has a HEALTHCHECK that native volume-init hooks cannot disable. Use HEALTHCHECK NONE in the image and define application healthchecks on the Compose service instead.")


# Verify that the final projection differs from the base projection only by the generated hook.
def validate_realized(base: Projection, final: Projection, initialization: Initialization) -> None:
    # Compare every projected fact that the override must preserve.
    fields: tuple[tuple[str, object, object], ...] = (
        ("service", base.facts.service, final.facts.service),
        ("image", base.facts.image, final.facts.image),
        ("platform", base.facts.platform, final.facts.platform),
        ("user", base.facts.user, final.facts.user),
        ("working_directory", base.facts.working_directory, final.facts.working_directory),
        ("privileged", base.facts.privileged, final.facts.privileged),
        ("host_network", base.facts.host_network, final.facts.host_network),
        ("labels", base.facts.labels, final.facts.labels),
        ("mounts", base.facts.mounts, final.facts.mounts),
        ("networks", base.facts.networks, final.facts.networks),
        ("environment_files", base.facts.environment_files, final.facts.environment_files),
        ("declared_secrets", base.facts.declared_secrets, final.facts.declared_secrets),
        ("secrets", base.facts.secrets, final.facts.secrets),
        ("build", base.facts.build, final.facts.build),
    )

    # If any effective fact changed after rendering the override.
    for name, expected, actual in fields:
        # If the realized value differs from the validated base projection.
        if expected != actual:
            # Throw.
            raise RecipeUnresolved("services", f"The resolved configuration changed `{name}` after hook rendering.")

    # Require the other hook sequences to remain unchanged.
    base_hooks: HooksFacts = base.facts.hooks
    final_hooks: HooksFacts = final.facts.hooks
    if final_hooks.post_start != base_hooks.post_start or final_hooks.pre_stop != base_hooks.pre_stop:
        # Throw.
        raise RecipeUnresolved("services", "The resolved lifecycle hooks changed after hook rendering.")

    # Require the generated hook first and the recipe hooks in their original order.
    if len(final_hooks.pre_start) != len(base_hooks.pre_start) + 1 or final_hooks.pre_start[1:] != base_hooks.pre_start:
        # Throw.
        raise RecipeUnresolved("services", "The resolved pre-start hooks changed after hook rendering.")

    # Read the realized generated hook.
    generated: HookFacts = final_hooks.pre_start[0]

    # Require the fixed identity, labels, and validated command.
    expected_command: tuple[str, ...] = ("--from=0", f"+{initialization.uid}", *initialization.targets)
    if (
        generated.origin != "generated"
        or generated.labels.get(ROLE_LABEL) != "volume-init"
        or generated.command != expected_command
    ):
        # Throw.
        raise RecipeUnresolved("services", "The generated volume initialization hook is not faithful.")


# Require an exact set of label values.
def _validate_labels(value: Mapping[str, str], field: str, expected: Mapping[str, str]) -> None:
    # For each expected label name and value.
    for name, expected_value in expected.items():
        # If a required label is missing or incorrect.
        if value.get(name) != expected_value:
            # Throw.
            raise ConfigurationError(f"{field}.{name}", f"Must be `{expected_value}`.")
