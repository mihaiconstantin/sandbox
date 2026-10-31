# Imports.
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Import domain values.
from sandbox.domain import PROJECT_ROOT, Initialization, RecipeDefinition, SandboxPlan

# Import validation.
from sandbox.validation.identifiers import validate_identifier


# Build the sandbox-owned Compose override for one recipe source.
def render_override(plan: SandboxPlan, definition: RecipeDefinition, *, pre_start: list[dict[str, Any]] | None = None) -> str:
    # Require a project identifier that is safe in labels and container paths.
    validate_identifier(plan.project.name, "project")

    # Resolve the project directory to an absolute path.
    project_dir: Path = plan.project.directory.expanduser().resolve()

    # Compute the container directory for the project.
    target: str = f"{PROJECT_ROOT}/{plan.project.name}"

    # Build the override in the repository's four-space YAML style.
    lines: list[str] = [
        "services:",
        f"    {definition.service}:",
        "        labels:",
        f"            sb.managed: {quote_yaml('true')}",
        f"            sb.project: {quote_yaml(plan.project.name)}",
        f"            sb.resource: {quote_yaml('container')}",
        f"            sb.role: {quote_yaml('box')}",
        f"            sb.catalogue: {quote_yaml(definition.catalogue)}",
        f"            sb.recipe: {quote_yaml(definition.recipe)}",
        f"        working_dir: {quote_yaml(target)}",
        "        volumes:",
        f"            - type: {quote_yaml('bind')}",
        f"              source: {quote_yaml(str(project_dir))}",
        f"              target: {quote_yaml(target)}",
        "              bind:",
        "                  create_host_path: false",
    ]

    # Mount shared storage only in the selected primary service.
    for volume in plan.volumes:
        # Use the physical name as the Compose key as well as the Docker lookup name.
        lines.extend([
            f"            - type: {quote_yaml('volume')}",
            f"              source: {quote_yaml(volume.name)}",
            f"              target: {quote_yaml(volume.target)}",
        ])

    # If access hooks were prepared, replace the recipe sequence with the complete ordered list.
    if pre_start is not None:
        # Preserve literal shell dollars through Compose's next interpolation pass.
        lines.append(f"        pre_start: !override {json.dumps(_compose_literals(pre_start))}")

    # If the service requires secrets.
    if plan.secrets:
        # Add the service secret section.
        lines.append("        secrets:")

        # Add each secret in resolved order.
        for secret in plan.secrets:
            lines.append(f"            - {secret.alias}")

    # Add the default network and its ownership labels.
    lines.extend([
        "networks:",
        "    default:",
        "        labels:",
        f"            sb.managed: {quote_yaml('true')}",
        f"            sb.project: {quote_yaml(plan.project.name)}",
        f"            sb.resource: {quote_yaml('network')}",
    ])

    # If the service requires shared volumes, define them at the top level.
    if plan.volumes:
        # Sandbox provisions these resources separately from Compose.
        lines.append("volumes:")

        # Retain the physical names without project prefixes.
        for volume in plan.volumes:
            lines.extend([
                f"    {quote_yaml(volume.name)}:",
                "        external: true",
                f"        name: {quote_yaml(volume.name)}",
            ])

    # If the service requires secrets, define them at the top level.
    if plan.secrets:
        # Add the top-level secret section.
        lines.append("secrets:")

        # Add each secret definition in resolved order.
        for secret in plan.secrets:
            # Resolve the secret path so Compose does not depend on its own working directory.
            secret_path: Path = secret.host_path.expanduser().resolve()

            # Add the secret definition.
            lines.append(f"    {secret.alias}:")
            lines.append(f"        file: {quote_yaml(str(secret_path))}")

    # Return the complete override document.
    return "\n".join(lines) + "\n"


# Build the fixed ownership initializer used for validated volume targets.
def generated_initialization_hook(plan: SandboxPlan, initialization: Initialization) -> dict[str, Any]:
    # Keep temporary hook containers owned but distinct from the workspace.
    labels: dict[str, str] = {
        "sb.managed": "true",
        "sb.project": plan.project.name,
        "sb.resource": "container",
        "sb.role": "volume-init",
    }

    # Initialize only root-owned volume roots with the standard coreutils command.
    return {
        "user": "0:0",
        "cap_drop": ["ALL"],
        "cap_add": ["CHOWN", "DAC_OVERRIDE"],
        "entrypoint": ["/bin/chown"],
        "command": ["--from=0", f"+{initialization.uid}", *initialization.targets],
        "environment": {
            "LD_PRELOAD": "",
            "LD_LIBRARY_PATH": "",
            "LD_AUDIT": "",
        },
        "labels": labels,
    }


# Build the ordered startup hook sequence for one initialization.
def initialization_hooks(plan: SandboxPlan, recipe_hooks: list[dict[str, Any]], initialization: Initialization) -> list[dict[str, Any]]:
    # Start with the generated hook so ownership is prepared before recipe code runs.
    hooks: list[dict[str, Any]] = [generated_initialization_hook(plan, initialization)]

    # Preserve every recipe hook and its relative order.
    for hook in recipe_hooks:
        hooks.append(dict(hook))

    # Return the complete ordered sequence.
    return hooks


# Quote a string as a YAML double-quoted scalar.
def quote_yaml(value: str) -> str:
    # JSON string escaping is valid YAML for the scalar values used by the override.
    return json.dumps(value)


# Protect resolved values from a second Compose interpolation without changing mapping keys.
def _compose_literals(value: Any) -> Any:
    # If the value is a string, retain its literal dollar signs.
    if isinstance(value, str):
        # Return the escaped scalar.
        return value.replace("$", "$$")

    # If the value is a mapping, preserve its keys and escape its values.
    if isinstance(value, Mapping):
        # Prepare the escaped mapping.
        mapping: dict[str, Any] = {}

        # For each key and value in the mapping.
        for key, item in value.items():
            # Compose literals.
            mapping[key] = _compose_literals(item)

        # Return the escaped mapping.
        return mapping

    # If the value is an array, escape each element in order.
    if isinstance(value, list):
        # Prepare the escaped array.
        items: list[Any] = []

        # For each element in the array.
        for element in value:
            # Compose literals.
            items.append(_compose_literals(element))

        # Return the escaped array.
        return items

    # Return non-string scalar values unchanged.
    return value


# Define the public API of the Compose override renderer.
__all__: list[str] = [
    "generated_initialization_hook",
    "initialization_hooks",
    "quote_yaml",
    "render_override",
]
