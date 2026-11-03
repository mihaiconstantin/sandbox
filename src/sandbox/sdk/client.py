# Imports.
from __future__ import annotations

from pathlib import Path

# Import the internal configuration facade.
from sandbox.configuration.store import ConfigurationStore

# Import the neutral ports and output default.
from sandbox.ports.builder import Builder
from sandbox.ports.output import SILENT, OutputSink
from sandbox.ports.runtime import Runtime

# Import the SDK operation objects.
from sandbox.sdk.boxes import BoxOperations
from sandbox.sdk.catalogues import CatalogueOperations
from sandbox.sdk.secrets import SecretOperations
from sandbox.sdk.volumes import VolumeOperations


# Own one configuration home and expose the four public SDK operation objects.
class SandboxClient:
    # Bind the client to its home and explicit neutral collaborators.
    def __init__(
        self,
        *,
        home: Path,
        runtime: Runtime,
        builder: Builder,
        output: OutputSink | None = None,
    ) -> None:
        # Require the configuration home and the two neutral ports.
        if not isinstance(home, Path):
            # Throw a programming error for Python API misuse.
            raise TypeError("home must be a path.")
        if not isinstance(runtime, Runtime):
            # Throw a programming error for Python API misuse.
            raise TypeError("runtime must implement the Runtime port.")
        if not isinstance(builder, Builder):
            # Throw a programming error for Python API misuse.
            raise TypeError("builder must implement the Builder port.")

        # Normalize the optional output sink to the stateless silent default.
        sink: OutputSink = SILENT if output is None else output

        # Require the selected sink to implement the output port.
        if not isinstance(sink, OutputSink):
            # Throw a programming error for Python API misuse.
            raise TypeError("output must implement the OutputSink port.")

        # Retain the home exactly as supplied without resolving or reading it.
        self._home: Path = home

        # Construct the client-owned configuration store without reading the home.
        store: ConfigurationStore = ConfigurationStore(home)

        # Eagerly construct the four operation objects and share the store.
        self._catalogues: CatalogueOperations = CatalogueOperations(store)
        self._secrets: SecretOperations = SecretOperations(store)
        self._volumes: VolumeOperations = VolumeOperations(runtime, sink)
        self._boxes: BoxOperations = BoxOperations(runtime, builder, self._catalogues, self._secrets, sink)

    # Expose the configuration home supplied at construction.
    @property
    def home(self) -> Path:
        # Return the home exactly as supplied.
        return self._home

    # Expose the box operations.
    @property
    def boxes(self) -> BoxOperations:
        # Return the eagerly constructed box operations.
        return self._boxes

    # Expose the shared-volume operations.
    @property
    def volumes(self) -> VolumeOperations:
        # Return the eagerly constructed volume operations.
        return self._volumes

    # Expose the catalogue operations.
    @property
    def catalogues(self) -> CatalogueOperations:
        # Return the eagerly constructed catalogue operations.
        return self._catalogues

    # Expose the secret operations.
    @property
    def secrets(self) -> SecretOperations:
        # Return the eagerly constructed secret operations.
        return self._secrets
