# Imports.
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Import domain values.
from sandbox.domain import PROJECT_ROOT, Initialization, RecipeDefinition, SandboxPlan

# Import validation.
from sandbox.validation.identifiers import validate_identifier


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
