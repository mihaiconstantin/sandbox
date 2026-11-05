# Imports.
from __future__ import annotations

from typing import NoReturn

import click
from rich.console import Console

# Import the public error root and structured command facts.
from sandbox.errors.base import CommandFailure, SandboxError

# Import the new public error classes by domain.
from sandbox.errors.boxes import (
    BoxAmbiguous,
    BoxNotFound,
    BoxNotReady,
    BoxNotRunning,
    BoxStateError,
)
from sandbox.errors.capabilities import ArtifactRejected, UnsupportedFeature, UnsupportedOperation
from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed
from sandbox.errors.create import CreateFailed, CreatePostconditionFailed
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.errors.ownership import OwnershipViolation
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind
from sandbox.errors.recipes import RecipeUnresolved
from sandbox.errors.removal import IncompleteRemoval, NetworkInUse, NothingToRemove
from sandbox.errors.terminal import InteractiveTerminalRequired
from sandbox.errors.volumes import (
    VolumeCreateFailed,
    VolumeInUse,
    VolumeNotFound,
    VolumeOwnershipError,
    VolumeReferencesUnavailable,
)
from sandbox.errors.build import BuildFailed

# Import display sanitization.
from sandbox.cli.presentation.text import sanitize_value

# Import the runtime vocabulary used for backend nouns.
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary


# Render one backend noun pair from the error label and the supplied vocabulary.
def backend_nouns(error_backend: str | None, vocabulary: RuntimeVocabulary) -> tuple[str, str, str]:
    # Use the composition vocabulary when the labels agree.
    if error_backend is None or error_backend == vocabulary.backend:
        # Return the supplied backend, singular, and plural nouns.
        return vocabulary.backend, vocabulary.noun, vocabulary.plural

    # Fall back to neutral nouns for an unknown backend label.
    return error_backend, "box", "boxes"


# Render one command failure using the compatibility command template.
def command_failure_message(failure: CommandFailure) -> str:
    # Keep the bounded diagnostic when one exists.
    detail: str = f": {failure.diagnostic}" if failure.diagnostic else ""

    # Report a timeout without inventing a command status.
    if failure.timed_out:
        # Return the timeout message.
        return f"The {failure.operation} operation timed out."

    # Report the exact argv when the adapter recorded one.
    if failure.command:
        # Join the argv into a display command.
        command: str = " ".join(failure.command)

        # Return the compatibility engine-failure text.
        return f"`{command}` failed with exit code {failure.exit_code}{detail}."

    # Otherwise name the operation without a command.
    return f"The {failure.operation} operation failed{detail}."


# Render one prerequisite failure with the documented actionable text.
def prerequisite_message(error: PrerequisiteError) -> str:
    # Read the structured facts.
    tool: str = error.tool
    diagnostic: str = error.diagnostic
    found: str | None = error.found
    requirement: str | None = error.requirement

    # Render Docker CLI prerequisites.
    if tool == "docker":
        # Report a missing executable.
        if error.kind is PrerequisiteKind.MISSING:
            # Return the actionable install hint.
            return "required executable `docker` was not found on PATH. Install Docker Engine and ensure it is on PATH."

        # Report an unreachable daemon or permission failure.
        if error.kind is PrerequisiteKind.UNUSABLE:
            # Keep the diagnostic when one was captured.
            suffix: str = f": {diagnostic}" if diagnostic else ""

            # Return the daemon hint.
            return f"Docker is installed but the daemon is not reachable{suffix}. Start Docker or check `DOCKER_HOST`."

        # Report an unsupported Docker version.
        version: str = found or "unknown"
        required: str = requirement or "a supported version"
        return f"Docker {version} is not supported; version {required} or newer is required."

    # Render Docker Compose prerequisites.
    if tool == "docker compose":
        # Report a missing plugin.
        if error.kind is PrerequisiteKind.MISSING:
            # Return the plugin install hint.
            return "Docker Compose is required but `docker compose` is not available. Install the Compose plugin (>= 5.6.0)."

        # Report a version floor failure.
        if error.kind is PrerequisiteKind.VERSION:
            # Use the documented floor when facts omit it.
            required = requirement or "5.6.0"
            return f"Docker Compose {found or 'unknown'} is too old; version {required.removeprefix('>=').strip()} or newer is required."

        # Report an unusable Compose installation.
        suffix = f": {diagnostic}" if diagnostic else ""
        return f"Docker Compose is installed but unusable{suffix}."

    # Render Buildx prerequisites.
    if tool in ("buildx", "docker buildx"):
        # Report a missing plugin only when a build is needed.
        if error.kind is PrerequisiteKind.MISSING:
            # Return the build-only install hint.
            return "Docker Buildx is required to build this recipe but the `buildx` plugin was not found. Install Buildx >= 0.17.0."

        # Report a version floor failure.
        if error.kind is PrerequisiteKind.VERSION:
            # Use the documented floor when facts omit it.
            required = requirement or "0.17.0"
            return f"Docker Buildx {found or 'unknown'} is too old; version {required.removeprefix('>=').strip()} or newer is required."

        # Report an unusable Buildx installation.
        suffix = f": {diagnostic}" if diagnostic else ""
        return f"Docker Buildx is installed but unusable{suffix}."

    # Render Git prerequisites for catalogue installation.
    if tool == "git":
        # Report a missing executable.
        if error.kind is PrerequisiteKind.MISSING:
            # Return the install hint.
            return "`git` is required to install `git` catalogue sources but was not found. Install git and ensure it is on PATH."

        # Keep an explicit hint or diagnostic for other git failures.
        return error.hint or error.diagnostic or f"`git` is {error.kind.value}."

    # Render a future microsandbox prerequisite.
    if tool == "microsandbox":
        # Report a missing runtime.
        if error.kind is PrerequisiteKind.MISSING:
            # Return the runtime install hint.
            return "The `microsandbox` runtime is not installed. Install microsandbox and retry."

        # Report an unusable runtime.
        suffix = f": {diagnostic}" if diagnostic else ""
        return f"The `microsandbox` runtime is installed but unusable{suffix}. Run `msb doctor` for details."

    # Keep an explicit hint for any future tool.
    if error.hint:
        # Return the supplied hint.
        return error.hint

    # Return the structured generic prerequisite message.
    suffix = f": {diagnostic}" if diagnostic else ""
    return f"Prerequisite `{tool}` is {error.kind.value}{suffix}."


# Present the public error family as one plain stderr failure.
class ErrorPresenter:
    # Bind the presenter to the composition-supplied runtime vocabulary.
    def __init__(self, vocabulary: RuntimeVocabulary, *, console: Console | None = None) -> None:
        # Retain the vocabulary used for absent-resource nouns.
        self.vocabulary: RuntimeVocabulary = vocabulary

        # Retain the one stderr console when presentation supplied it.
        self.console: Console | None = console

    # Render one public error to its compatibility message.
    def render(self, error: SandboxError) -> str:
        # Read the backend vocabulary nouns for this failure.
        backend, noun, plural = backend_nouns(getattr(error, "backend", None), self.vocabulary)

        # Render box state failures before lookup failures.
        if isinstance(error, BoxNotReady):
            # Return the partial-creation recovery message.
            return f"The `{backend}` {noun} for project `{error.name}` has not completed creation. Rerun `sb create box` with its recipe and project directory."

        # Render non-running boxes.
        if isinstance(error, BoxNotRunning):
            # Return the not-running message.
            return f"The `{backend}` {noun} for project `{error.name}` is not running."

        # Render the generic state condition.
        if isinstance(error, BoxStateError):
            # Keep the supplied detail when one exists.
            detail: str = f": {error.detail}" if error.detail else ""
            return f"Box `{error.name}` is not in a usable state{detail}."

        # Render absent boxes.
        if isinstance(error, BoxNotFound):
            # Return the compatibility lookup message.
            return f"No `{backend}` {noun} exists for project `{error.name}`."

        # Render ambiguous boxes.
        if isinstance(error, BoxAmbiguous):
            # Return the compatibility ambiguity message.
            return f"Multiple `{backend}` {plural} exist for project `{error.name}`."

        # Render volume ownership failures.
