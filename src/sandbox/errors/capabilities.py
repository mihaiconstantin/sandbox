# Imports.
from __future__ import annotations

# Import the public root.
from sandbox.errors.base import SandboxError


# Represent a runtime capability that cannot satisfy a request.
class CapabilityError(SandboxError):
    # Construct the error from the feature and its optional facts.
    def __init__(self, feature: str, detail: str = "", backend: str | None = None) -> None:
        # Record the capability facts.
        self.backend: str | None = backend
        self.feature: str = feature
        self.detail: str = detail

        # Initialize the error with a neutral capability message.
        super().__init__(detail or f"The configured runtime does not support {feature}.")


# Represent a runtime feature that is not supported.
class UnsupportedFeature(CapabilityError):
    # No additional behavior.
    pass


# Represent a runtime operation that is not supported.
class UnsupportedOperation(UnsupportedFeature):
    # Construct the error from the operation and its optional facts.
    def __init__(self, operation: str, detail: str = "", backend: str | None = None) -> None:
        # Record the unsupported operation.
        self.operation: str = operation

        # Initialize the capability error for the operation.
        super().__init__(operation, detail or f"Operation `{operation}` is not supported by the configured runtime.", backend)


# Represent a build artifact the runtime cannot accept.
class ArtifactRejected(CapabilityError):
    # Construct the error from the artifact facts.
    def __init__(
        self,
        transport: str,
        reference: str | None = None,
        expected_platform: str | None = None,
        actual_platform: str | None = None,
        detail: str = "",
        backend: str | None = None,
    ) -> None:
        # Record the artifact facts.
        self.transport: str = transport
        self.reference: str | None = reference
        self.expected_platform: str | None = expected_platform
        self.actual_platform: str | None = actual_platform

        # Initialize the capability error for the artifact.
        super().__init__("artifact", detail or "The build artifact cannot be used by the runtime.", backend)
