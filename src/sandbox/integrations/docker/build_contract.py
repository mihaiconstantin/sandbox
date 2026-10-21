# Imports.
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import public input and recipe errors.
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.recipes import RecipeUnresolved

# Import the neutral plan and recipe values.
from sandbox.domain import RecipeDefinition, SandboxPlan


# Record the local build descriptor read from one resolved Compose service.
@dataclass(frozen = True, slots = True)
class BuildDeclaration:
    # Record the contained absolute build context.
    context: Path

    # Record the contained absolute Dockerfile when one was declared.
    dockerfile: Path | None


# Record the effective image and optional build declaration for one service.
@dataclass(frozen = True, slots = True)
class ServiceBuild:
    # Record the effective Compose image reference.
    image: str

    # Record the effective service platform when one is resolved.
    platform: str | None

    # Record the build declaration when the service declares a build.
    build: BuildDeclaration | None
