# Imports.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

# Import the neutral domain values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BuildArtifact,
    RecipeDefinition,
    SandboxPlan,
)

# Import the neutral errors.
from sandbox.errors import SandboxError
from sandbox.errors.capabilities import ArtifactRejected

# Import the output port values.
from sandbox.ports.output import SILENT, OutputSink, ProgressPhase


# Represent one recorded artifact preparation request.
@dataclass(frozen = True, slots = True)
class PrepareRequest:
    # Record the neutral plan.
    plan: SandboxPlan

    # Record the opaque recipe source.
    definition: RecipeDefinition

    # Record the runtime's artifact requirement.
    requirement: ArtifactRequirement

    # Report whether a rebuild was requested.
    rebuild: bool

    # Record the caller-owned staging directory.
    staging_dir: Path | None


# Represent a stateful fake builder that records artifact preparations.
class FakeBuilder:
    # Construct a builder with an optional build declaration and archive contents.
    def __init__(self, *, buildable: bool = True, archive_contents: bytes = b"fake archive") -> None:
        # Require exact configuration facts.
        if type(buildable) is not bool:
            # Throw.
            raise ValueError("buildable must be a Boolean.")
        if not isinstance(archive_contents, bytes):
            # Throw.
            raise ValueError("archive_contents must be bytes.")

        # Store the behavior configuration and the prepared image store.
        self.buildable: bool = buildable
        self.archive_contents: bytes = archive_contents
        self.images: set[str] = set()
        self.requests: list[PrepareRequest] = []
        self._faults: deque[SandboxError] = deque()

    # Queue a preparation failure.
    def fail_next(self, error: SandboxError) -> None:
        # Require a neutral error.
        if not isinstance(error, SandboxError):
            # Throw a programming error.
            raise ValueError("Faults must be neutral sandbox errors.")

        # Record the failure.
        self._faults.append(error)

    # Ensure the required image exists and return the typed artifact.
    def prepare(
        self,
        plan: SandboxPlan,
        definition: RecipeDefinition,
        requirement: ArtifactRequirement,
        *,
        rebuild: bool = False,
        staging_dir: Path | None = None,
        output: OutputSink = SILENT,
    ) -> BuildArtifact:
        # Apply a queued fault before preparation.
        if self._faults:
            # Raise the next fault.
            raise self._faults.popleft()

        # Require the neutral request values.
        if not isinstance(requirement, ArtifactRequirement):
            # Throw.
            raise ValueError("requirement must be an ArtifactRequirement.")
        if type(rebuild) is not bool:
            # Throw.
            raise ValueError("rebuild must be a Boolean.")
        if staging_dir is not None and not isinstance(staging_dir, Path):
            # Throw.
            raise ValueError("staging_dir must be a path or `None`.")

        # Reject an unimplemented transport before preparing any image.
        if requirement.transport is ArtifactTransport.OCI_ARCHIVE:
            # Throw.
            raise ArtifactRejected(transport = requirement.transport.value, reference = requirement.reference, detail = "OCI archives are not implemented.")

        # Require operation-scoped staging for a byte-carrying transport.
        archive_dir: Path | None = staging_dir if requirement.transport is not ArtifactTransport.LOCAL_IMAGE else None
        if requirement.transport is not ArtifactTransport.LOCAL_IMAGE and archive_dir is None:
            # Throw.
            raise ValueError("Archive transports require a staging directory.")

        # Record the request.
        self.requests.append(PrepareRequest(plan = plan, definition = definition, requirement = requirement, rebuild = rebuild, staging_dir = staging_dir))

        # Report whether this call must make the image exist.
        created: bool = False

        # If the image is missing.
        if requirement.reference not in self.images:
            # Record the prepared image.
            self.images.add(requirement.reference)
            created = True

            # Emit the build phase only for an actual build, never a pull.
            if self.buildable:
                # Report the build.
                output.progress(ProgressPhase.BUILD_IMAGE, subject = definition.service)

        # If a buildable image is present and a rebuild was requested.
        elif rebuild and self.buildable:
            # Report the rebuild without treating the image as newly pulled.
            created = True
            output.progress(ProgressPhase.BUILD_IMAGE, subject = definition.service)

        # Write one archive for a byte-carrying transport.
        archive_path: Path | None = None
        if archive_dir is not None:
            # Write the operation-scoped archive.
            archive_path = archive_dir / "artifact.tar"
            archive_path.write_bytes(self.archive_contents)

        # Return the artifact matching the requirement.
        return BuildArtifact(
            reference = requirement.reference,
            platform = requirement.platform,
            digest = None,
            transport = requirement.transport,
            archive_path = archive_path,
            created = created,
        )
