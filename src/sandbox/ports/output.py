# Imports.
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


# Represent the closed, backend-neutral progress vocabulary.
class ProgressPhase(StrEnum):
    # The caller is about to prepare the image through the builder.
    PREPARE_IMAGE = "prepare-image"

    # The builder started an actual build, never a pull or reuse.
    BUILD_IMAGE = "build-image"

    # The caller is ensuring one declared shared volume.
    ENSURE_VOLUME = "ensure-volume"

    # The caller is about to create and start the box.
    CREATE = "create"

    # The caller is about to start a box.
    START = "start"

    # The caller is about to stop a box.
    STOP = "stop"

    # The caller is about to remove a box.
    REMOVE = "remove"

    # The caller is about to remove a shared volume.
    REMOVE_VOLUME = "remove-volume"


# Represent the child stream an opaque process chunk arrived on.
class OutputChannel(StrEnum):
    # The child wrote to standard output.
    STDOUT = "stdout"

    # The child wrote to standard error.
    STDERR = "stderr"


# Represent the optional receiver for advisory progress and child-process output.
@runtime_checkable
class OutputSink(Protocol):
    # Report one advisory progress phase with an optional untrusted subject.
    def progress(self, phase: ProgressPhase, *, subject: str | None = None) -> None: ...

    # Forward one opaque child-process chunk on its original channel.
    def process_output(self, channel: OutputChannel, data: bytes) -> None: ...


# Represent a stateless sink that discards every advisory event.
@dataclass(frozen = True, slots = True)
class _SilentOutput:
    # Discard one progress phase.
    def progress(self, phase: ProgressPhase, *, subject: str | None = None) -> None:
        # Do nothing; the silent sink is a no-op.
        return None

    # Discard one child-process chunk.
    def process_output(self, channel: OutputChannel, data: bytes) -> None:
        # Do nothing; the silent sink is a no-op.
        return None


# Define the shared stateless silent default.
SILENT: OutputSink = _SilentOutput()


# Define the public API of the `sandbox.ports.output` module.
__all__: list[str] = ["OutputChannel", "OutputSink", "ProgressPhase", "SILENT"]
