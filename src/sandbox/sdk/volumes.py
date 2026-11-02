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
