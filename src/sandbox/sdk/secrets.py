# Imports.
from __future__ import annotations

from pathlib import Path

# Import the internal configuration facade.
from sandbox.configuration.store import ConfigurationStore

# Import the registry-facing secret binding.
from sandbox.domain.registry import SecretBinding

# Import the shared identifier rule.
from sandbox.validation.identifiers import validate_identifier


# Expose catalogue-scoped secret bindings without reading secret contents.
class SecretOperations:
    # Bind the operations to the client-owned configuration store.
    def __init__(self, store: ConfigurationStore) -> None:
        # Retain the configuration store.
        self._store: ConfigurationStore = store
