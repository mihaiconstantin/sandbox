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


# Project the effective image, platform, and build declaration for one recipe service.
def project_service(
    configuration: Mapping[str, Any],
    plan: SandboxPlan,
    definition: RecipeDefinition,
    *,
    default_platform: str | None = None,
) -> ServiceBuild:
    # Require a top-level mapping and a services table.
    configuration = _mapping(configuration, "configuration")
    services: Mapping[str, Any] = _mapping(configuration.get("services"), "services")

    # Require the selected primary service.
    if definition.service not in services:
        # Throw.
        raise RecipeUnresolved("services", f"Primary service `{definition.service}` is not declared in the resolved recipe configuration.")

    # Require a mapping for the selected service.
    field: str = f"services.{definition.service}"
    service: Mapping[str, Any] = _mapping(services[definition.service], field)

    # Read the effective image or reproduce Compose's default image name.
    image: Any = service.get("image")
    if image is None:
        # Use the Compose default for the selected project and service.
        image_name: str = f"{plan.project.name}-{definition.service}"
    elif isinstance(image, str) and image.strip():
        # Retain the declared image reference exactly as Compose resolved it.
        image_name = image
    else:
        # Throw.
        raise RecipeUnresolved(f"{field}.image", "Must be a nonblank image reference.")

    # Read the effective service platform without inventing one.
    platform_value: Any = service.get("platform")
    if platform_value is not None and (not isinstance(platform_value, str) or not platform_value.strip()):
        # Throw.
        raise RecipeUnresolved(f"{field}.platform", "Must be a nonblank platform string.")

    # Read the effective build declaration.
    build: BuildDeclaration | None = _build(service.get("build"), definition.catalogue_root, f"{field}.build")

    # Apply the Docker default platform only to a locally built service, matching the current projection.
    effective_platform: str | None = platform_value if platform_value is not None else (default_platform if build is not None else None)

    # Return the effective service facts.
    return ServiceBuild(image = image_name, platform = effective_platform, build = build)


# Project one contained local build declaration.
def _build(value: object, catalogue_root: Path, field: str) -> BuildDeclaration | None:
    # If no build is declared, return no descriptor.
    if value is None:
        # Return no build.
        return None

    # Read the short string form.
    if isinstance(value, str):
        # Require the short context form to be nonblank.
        if not value.strip():
            # Throw.
            raise RecipeUnresolved(field, "Must be a nonblank local build context.")

        # Build the short descriptor.
        build: Mapping[str, Any] = {"context": value}

    # Otherwise require a build mapping.
    else:
        # Normalize the mapping form.
        build = _mapping(value, field)

    # Resolve the local build context against the catalogue root.
    context: Path = _contained_local_path(build.get("context", "."), catalogue_root, f"{field}.context")

    # Require the build context to exist as a directory.
    if not context.is_dir():
        # Throw.
        raise ConfigurationError(f"{field}.context", "Must reference an existing local directory.")

    # Resolve an optional Dockerfile against the build context.
    dockerfile_value: Any = build.get("dockerfile")
    dockerfile: Path | None = None
    if dockerfile_value is not None:
        # Require a nonblank Dockerfile path.
        if not isinstance(dockerfile_value, str) or not dockerfile_value.strip():
            # Throw.
            raise RecipeUnresolved(f"{field}.dockerfile", "Must be a nonblank local path.")

        # Resolve the path against the context before containment checks.
        dockerfile_path: Path = Path(dockerfile_value).expanduser()
        if not dockerfile_path.is_absolute():
            # Anchor the Dockerfile at the build context.
            dockerfile_path = context / dockerfile_path

        # Require the Dockerfile to remain inside the catalogue.
        dockerfile = _contained_path(dockerfile_path, catalogue_root, f"{field}.dockerfile")

        # Require the Dockerfile to exist as a regular file.
        if not dockerfile.is_file():
            # Throw.
            raise ConfigurationError(f"{field}.dockerfile", "Must reference an existing file.")

    # Reject build arguments that cannot be resolved to one explicit value.
    _validate_build_arguments(build.get("args"), f"{field}.args")

    # Validate every additional context and reject remote sources.
    _validate_additional_contexts(build.get("additional_contexts"), catalogue_root, f"{field}.additional_contexts")

    # Return the contained build descriptor.
    return BuildDeclaration(context = context, dockerfile = dockerfile)


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


# Require a mapping value at one resolved-configuration field.
def _mapping(value: object, field: str) -> Mapping[str, Any]:
    # If the value is not a mapping.
    if not isinstance(value, Mapping):
        # Throw.
        raise RecipeUnresolved(field, "Must be a mapping.")

    # Return the mapping.
    return value


# Define the public API of the builder build-contract projection.
__all__: list[str] = ["BuildDeclaration", "ServiceBuild", "project_service"]
