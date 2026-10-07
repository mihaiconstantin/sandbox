# Imports.
from sandbox.errors.base import CommandFailure, InputError, SandboxError
from sandbox.errors.boxes import (
    BoxAmbiguous,
    BoxLookupError,
    BoxNotFound,
    BoxNotReady,
    BoxNotRunning,
    BoxStateError,
)
from sandbox.errors.build import BuildError, BuildFailed
from sandbox.errors.capabilities import (
    ArtifactRejected,
    CapabilityError,
    UnsupportedFeature,
    UnsupportedOperation,
)
from sandbox.errors.catalogues import CatalogueError, CatalogueInstallError, RegistryError
from sandbox.errors.configuration import ConfigurationError, RootExecutionNotAllowed
from sandbox.errors.create import CreateError, CreateFailed, CreatePostconditionFailed
from sandbox.errors.engine import EngineError, EngineFailure, EngineOutputInvalid
from sandbox.errors.ownership import OwnershipViolation
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind
from sandbox.errors.recipes import RecipeError, RecipeUnresolved
from sandbox.errors.removal import IncompleteRemoval, NetworkInUse, NothingToRemove, RemovalError
from sandbox.errors.secrets import MissingSecret, SecretError, SecretFileError
from sandbox.errors.terminal import InteractiveTerminalRequired, TerminalError
from sandbox.errors.volumes import (
    VolumeCreateFailed,
    VolumeError,
    VolumeInUse,
    VolumeNotFound,
    VolumeOwnershipError,
    VolumeReferencesUnavailable,
)
