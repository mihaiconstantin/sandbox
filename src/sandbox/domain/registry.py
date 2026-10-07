# Imports.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Import the shared invariant helpers.
from sandbox.domain._invariants import _require_nonblank, _require_path


# Require a secret alias usable as one file name.
def _require_alias(value: object, field: str) -> str:
    # Require a nonblank alias first.
    value = _require_nonblank(value, field)

    # If the alias contains a path separator, traversal, or unsupported characters.
    if re.fullmatch(r"[A-Za-z0-9._-]+", value) is None or value in (".", ".."):
        # Throw.
        raise ValueError(f"{field} must be one file name containing only letters, digits, periods, hyphens, or underscores.")

    # Return the validated alias.
    return value


# Represent a catalogue-scoped secret binding loaded for an operation.
@dataclass(frozen = True, slots = True)
class CatalogueBinding:
    # Record the catalogue-local secret alias.
    alias: str

    # Record the resolved host secret file.
    path: Path

    def __post_init__(self) -> None:
        # Require a usable alias and host file.
        _require_alias(self.alias, "CatalogueBinding.alias")
        _require_path(self.path, "CatalogueBinding.path")


# Represent a registered catalogue and its configured location.
@dataclass(frozen = True, slots = True)
class CatalogueRegistration:
    # Record the registered catalogue name.
    name: str

    # Record the registered origin.
    type: str

    # Record the resolved catalogue directory.
    path: Path

    # Record the catalogue-scoped secret bindings when loaded for removal.
    bindings: tuple[CatalogueBinding, ...] = ()

    def __post_init__(self) -> None:
        # Require catalogue identity and a resolved location.
        _require_nonblank(self.name, "CatalogueRegistration.name")
        _require_nonblank(self.type, "CatalogueRegistration.type")
        _require_path(self.path, "CatalogueRegistration.path")

        # Require an immutable tuple of bindings.
        if not isinstance(self.bindings, tuple) or any(not isinstance(binding, CatalogueBinding) for binding in self.bindings):
            # Throw.
            raise ValueError("CatalogueRegistration.bindings must be a tuple of CatalogueBinding values.")

        # Require unique binding aliases.
        aliases: set[str] = set()

        # For each binding.
        for binding in self.bindings:
            # If the alias repeats.
            if binding.alias in aliases:
                # Throw.
                raise ValueError("CatalogueRegistration.bindings must have unique aliases.")

            # Record the alias.
            aliases.add(binding.alias)


# Represent a secret binding stored for one catalogue alias.
@dataclass(frozen = True, slots = True)
class SecretBinding:
    # Record the catalogue that scopes the binding.
    catalogue: str

    # Record the catalogue-local secret alias.
    alias: str

    # Record the resolved host secret file.
    host_path: Path

    def __post_init__(self) -> None:
        # Require the catalogue identity, a usable alias, and a host file.
        _require_nonblank(self.catalogue, "SecretBinding.catalogue")
        _require_alias(self.alias, "SecretBinding.alias")
        _require_path(self.host_path, "SecretBinding.host_path")


# Represent a registered catalogue scheduled for removal.
@dataclass(frozen = True, slots = True)
class CatalogueRemovalPlan:
    # Record the configuration home the registration belongs to.
    home: Path

    # Record the registered catalogue and its bindings.
    registration: CatalogueRegistration

    def __post_init__(self) -> None:
        # Require the configuration home.
        _require_path(self.home, "CatalogueRemovalPlan.home")

        # Require the loaded registration.
        if not isinstance(self.registration, CatalogueRegistration):
            # Throw.
            raise ValueError("CatalogueRemovalPlan.registration must be a CatalogueRegistration value.")
