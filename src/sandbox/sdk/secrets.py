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

    # List every configured secret binding.
    def list(self) -> tuple[SecretBinding, ...]:
        # Return the validated configuration bindings.
        return self._store.secret_bindings()

    # Read one catalogue-scoped secret binding, or report absence.
    def get(self, catalogue: str, alias: str) -> SecretBinding | None:
        # Validate the configuration keys before reading the binding.
        validate_identifier(catalogue, "catalogue")
        validate_identifier(alias, "secret")

        # Return the validated binding or its absence.
        return self._store.secret_binding(catalogue, alias)

    # Bind a host secret file to a catalogue-scoped alias.
    def bind(self, catalogue: str, alias: str, host_file: Path) -> SecretBinding:
        # Validate the configuration keys before checking the catalogue.
        validate_identifier(catalogue, "catalogue")
        validate_identifier(alias, "secret")

        # Require a host file path.
        if not isinstance(host_file, Path):
            # Throw a programming error for Python API misuse.
            raise TypeError("host_file must be a path.")

        # Require the catalogue to be registered and resolvable.
        self._store.require(catalogue)

        # Save the binding without reading the secret contents.
        return self._store.save_secret(catalogue, alias, host_file)
