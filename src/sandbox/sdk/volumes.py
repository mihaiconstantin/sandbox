# Imports.
from __future__ import annotations

# Import the observed volume values.
from sandbox.domain.volume import EnsuredVolume, VolumeInfo

# Import the runtime port and its silent output default.
from sandbox.ports.output import OutputSink, ProgressPhase
from sandbox.ports.runtime import Runtime

# Import the shared physical volume-name rule.
from sandbox.validation.identifiers import validate_volume_name


# Expose the shared-volume use cases over one runtime.
class VolumeOperations:
    # Bind the operations to their runtime and output sink.
    def __init__(self, runtime: Runtime, output: OutputSink) -> None:
        # Retain the runtime and the advisory sink.
        self._runtime: Runtime = runtime
        self._output: OutputSink = output

    # Ensure one shared volume exists and report whether this call created it.
    def ensure(self, name: str) -> EnsuredVolume:
        # Reject an invalid physical volume name before reaching the runtime.
        validate_volume_name(name)

        # Report the volume phase before the runtime call.
        self._output.progress(ProgressPhase.ENSURE_VOLUME, subject = name)

        # Ensure the volume through the runtime port.
        return self._runtime.ensure_volume(name)

    # Observe one managed shared volume by name, or report absence.
    def get(self, name: str) -> VolumeInfo | None:
        # Reject an invalid physical volume name before reaching the runtime.
        validate_volume_name(name)

        # Return the observed volume or the proven absence.
        return self._runtime.inspect_volume(name)
