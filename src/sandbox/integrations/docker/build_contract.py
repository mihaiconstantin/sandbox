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


# Reject a build argument that has no explicit value.
def _validate_build_arguments(value: object, field: str) -> None:
    # If no arguments are declared, accept the build.
    if value is None:
        # Return without arguments.
        return

    # Normalize the resolved mapping form.
    if isinstance(value, Mapping):
        # Validate every named argument.
        for name, item in value.items():
            # Require a usable name.
            if not isinstance(name, str) or not name.strip():
                # Throw.
                raise ConfigurationError(field, "Must contain nonblank build-argument names.")

            # Reject an unresolved or non-scalar value.
            if item is None or not isinstance(item, str):
                # Throw.
                raise ConfigurationError(f"{field}.{name}", "Must declare an explicit build-argument value.")

        # Return after validating the mapping.
        return

    # Normalize the resolved array form.
    if isinstance(value, list):
        # Validate every array entry.
        for index, item in enumerate(value):
            # Require the `name=value` form.
            if not isinstance(item, str) or "=" not in item:
                # Throw.
                raise ConfigurationError(f"{field}[{index}]", "Must declare an explicit `name=value` build argument.")

            # Require a nonblank argument name.
            name: str = item.split("=", 1)[0]
            if not name.strip():
                # Throw.
                raise ConfigurationError(f"{field}[{index}]", "Must declare a nonblank build-argument name.")

        # Return after validating the array.
        return

    # Reject an unexpected resolved shape.
    raise RecipeUnresolved(field, "Must be a mapping or an array of `name=value` strings.")


# Validate local additional build contexts while preserving Compose service references.
def _validate_additional_contexts(value: object, catalogue_root: Path, field: str) -> None:
    # If no additional contexts are declared, accept the build.
    if value is None:
        # Return without additional contexts.
        return

    # Normalize the mapping form.
    if isinstance(value, Mapping):
        # Read every declared context.
        entries: list[Any] = list(value.values())

    # Normalize the array form.
    elif isinstance(value, list):
        # Read every declared context.
        entries = list(value)

    # Reject an unexpected resolved shape.
    else:
        # Throw.
        raise RecipeUnresolved(field, "Must be a mapping or an array of context declarations.")

    # Validate every context entry.
    for index, entry in enumerate(entries):
        # Require a string entry.
        if not isinstance(entry, str) or not entry.strip():
            # Throw.
            raise RecipeUnresolved(f"{field}[{index}]", "Must be a nonblank context declaration.")

        # Preserve Compose service references without interpreting their build graph.
        if entry.startswith("service:"):
            # Accept the service reference.
            continue

        # Strip an optional `name=` prefix from the array form.
        context_value: str = entry.split("=", 1)[1] if "=" in entry else entry

        # Preserve a Compose service reference after the optional name prefix.
        if context_value.startswith("service:"):
            # Accept the service reference.
            continue

        # Reject remote, image, and git build contexts.
        if "://" in context_value or context_value.startswith("git@"):
            # Throw.
            raise ConfigurationError(f"{field}[{index}]", "Must use a local build context inside the catalogue directory.")

        # Require containment without requiring existence.
        _contained_local_path(context_value, catalogue_root, f"{field}[{index}]")


# Resolve one local path against the catalogue root and require containment.
def _contained_local_path(value: object, catalogue_root: Path, field: str) -> Path:
    # Require a nonblank string path.
    if not isinstance(value, str) or not value.strip():
        # Throw.
        raise RecipeUnresolved(field, "Must be a nonblank local path.")

    # Reject remote and image build sources.
    if "://" in value or value.startswith("git@") or value.startswith("service:"):
        # Throw.
        raise ConfigurationError(field, "Must use a local build context inside the catalogue directory.")

    # Expand the user and anchor relative paths at the catalogue root.
    path: Path = Path(value).expanduser()
    if not path.is_absolute():
        # Resolve against the catalogue root.
        path = catalogue_root / path

    # Require the resolved path to stay inside the catalogue.
    return _contained_path(path, catalogue_root, field)


# Require a path to resolve inside one directory.
def _contained_path(path: Path, directory: Path, field: str) -> Path:
    # Resolve candidate and root without requiring either to exist.
    resolved: Path = path.expanduser().resolve(strict = False)
    root: Path = directory.expanduser().resolve(strict = False)

    # If the path escapes the catalogue.
    if not resolved.is_relative_to(root):
        # Throw.
        raise ConfigurationError(field, "Must resolve inside the catalogue directory.")

    # Return the contained path.
    return resolved
