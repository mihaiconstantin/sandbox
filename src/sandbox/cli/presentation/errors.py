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
