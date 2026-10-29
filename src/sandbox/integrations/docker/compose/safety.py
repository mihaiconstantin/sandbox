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
