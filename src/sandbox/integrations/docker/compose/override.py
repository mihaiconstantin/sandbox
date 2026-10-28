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
