# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_guest_path, _require_nonblank, _require_path
from sandbox.domain.paths import PROJECT_ROOT, Workspace
from sandbox.domain.volume import VolumeDeclaration


# Represent a named binding between a project name and a host directory.
@dataclass(frozen = True)
class Project:
    # Identify the project and its box.
    name: str

    # Record the immutable host project directory.
    directory: Path

    def __post_init__(self) -> None:
        # Require a nonblank project name and a host directory.
        _require_nonblank(self.name, "Project.name")
        _require_path(self.directory, "Project.directory")


# Represent a named sensitive input resolved to one host file.
@dataclass(frozen = True)
class Secret:
    # Record the delivery alias and guest filename.
    alias: str

    # Record the resolved host file.
    host_path: Path

    def __post_init__(self) -> None:
        # Require an alias usable as one file name.
        _require_nonblank(self.alias, "Secret.alias")

        # If the alias contains a path separator or traversal.
        if re.fullmatch(r"[A-Za-z0-9._-]+", self.alias) is None or self.alias in (".", ".."):
            # Throw.
            raise ValueError("Secret.alias must be one file name containing only letters, digits, periods, hyphens, or underscores.")

        # Require the resolved host file path.
        _require_path(self.host_path, "Secret.host_path")


# Represent the neutral intent for one box creation.
@dataclass(frozen = True)
class SandboxPlan:
    # Record the project identity and host directory.
    project: Project

    # Record the live project bind and fixed target.
    workspace: Workspace

    # Record the required shared volumes.
    volumes: tuple[VolumeDeclaration, ...]

    # Record the resolved secret bindings.
    secrets: tuple[Secret, ...]

    # Record the recipe root policy.
    allow_root: bool

    def __post_init__(self) -> None:
        # Require the plan parts.
        if not isinstance(self.project, Project) or not isinstance(self.workspace, Workspace):
            # Throw.
            raise ValueError("SandboxPlan.project and SandboxPlan.workspace must be domain values.")

        # Require the workspace to describe the project directory at the fixed target.
        if self.workspace.host_directory != self.project.directory or self.workspace.target != f"{PROJECT_ROOT}/{self.project.name}":
            # Throw.
            raise ValueError("SandboxPlan.workspace must bind the project directory at the fixed project target.")

        # Require immutable volume and secret tuples.
        if not isinstance(self.volumes, tuple) or not isinstance(self.secrets, tuple):
            # Throw.
            raise ValueError("SandboxPlan.volumes and SandboxPlan.secrets must be tuples.")

        # Reject duplicate physical volume names and guest targets.
        volume_names: set[str] = set()
        volume_targets: set[str] = set()

        # For each volume declaration.
        for declaration in self.volumes:
            # If the declaration is not a volume declaration.
            if not isinstance(declaration, VolumeDeclaration):
                # Throw.
                raise ValueError("SandboxPlan.volumes must contain VolumeDeclaration values.")

            # If the physical name or target repeats.
            if declaration.name in volume_names or declaration.target in volume_targets:
                # Throw.
                raise ValueError("SandboxPlan.volumes must have unique physical names and guest targets.")

            # Record the declaration keys.
            volume_names.add(declaration.name)
            volume_targets.add(declaration.target)

        # Reject duplicate secret aliases.
        secret_aliases: set[str] = set()

        # For each secret binding.
        for secret in self.secrets:
            # If the binding is not a secret.
            if not isinstance(secret, Secret):
                # Throw.
                raise ValueError("SandboxPlan.secrets must contain Secret values.")

            # If the alias repeats.
            if secret.alias in secret_aliases:
                # Throw.
                raise ValueError("SandboxPlan.secrets must have unique aliases.")

            # Record the alias.
            secret_aliases.add(secret.alias)

        # Require an exact Boolean root policy.
        if type(self.allow_root) is not bool:
            # Throw.
            raise ValueError("SandboxPlan.allow_root must be a Boolean.")


# Represent the opaque recipe source passed to the builder and runtime.
@dataclass(frozen = True)
class RecipeDefinition:
    # Record the source catalogue name for provenance.
    catalogue: str

    # Record the effective recipe name for provenance.
    recipe: str

    # Record the catalogue root used as the project directory.
    catalogue_root: Path

    # Record the parent-first recipe source files.
    files: tuple[Path, ...]

    # Record the selected service selector, opaque to the core.
    service: str

    def __post_init__(self) -> None:
        # Require the source identity and selected service.
        _require_nonblank(self.catalogue, "RecipeDefinition.catalogue")
        _require_nonblank(self.recipe, "RecipeDefinition.recipe")
        _require_nonblank(self.service, "RecipeDefinition.service")

        # Require the catalogue root and a nonempty ordered file chain.
        _require_path(self.catalogue_root, "RecipeDefinition.catalogue_root")

        # If the file chain is not a nonempty tuple.
        if not isinstance(self.files, tuple) or not self.files:
            # Throw.
            raise ValueError("RecipeDefinition.files must be a nonempty tuple of paths.")

        # For each recipe source file.
        for path in self.files:
            # Require a path.
            _require_path(path, "RecipeDefinition.files")
