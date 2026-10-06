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
