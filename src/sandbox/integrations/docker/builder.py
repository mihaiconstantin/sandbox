# Imports.
from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Import the public typed errors raised by the builder.
from sandbox.errors.base import CommandFailure
from sandbox.errors.build import BuildFailed
from sandbox.errors.capabilities import ArtifactRejected
from sandbox.errors.engine import EngineFailure

# Import the neutral port and its values.
from sandbox.domain import (
    ArtifactRequirement,
    ArtifactTransport,
    BuildArtifact,
    RecipeDefinition,
    SandboxPlan,
)
from sandbox.ports.builder import Builder
from sandbox.ports.output import SILENT, OutputSink, ProgressPhase

# Import the ordinary helper values.
from sandbox.integrations.docker.build_contract import ServiceBuild, project_service
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.compose_cli import ComposeCli
from sandbox.integrations.docker.invocation import compose_environment
from sandbox.integrations.docker.preflight import require_buildx, require_compose

# Name the single archive produced for one operation.
ARCHIVE_NAME: str = "artifact.tar"

# Name the single image manifest inside a Docker archive.
ARCHIVE_MANIFEST: str = "manifest.json"


# Prepare Docker images and typed artifacts for a runtime requirement.
class DockerBuilder(Builder):
    # Construct the builder around one Docker gateway.
    def __init__(self, docker: DockerCli) -> None:
        # Record the shared gateway and its Compose facade.
        self._docker: DockerCli = docker
        self._compose: ComposeCli = ComposeCli(docker)

    # Reject transports the Docker builder does not implement before any work.
    def _require_supported_transport(self, requirement: ArtifactRequirement) -> None:
        # OCI archives remain a future transport.
        if requirement.transport is ArtifactTransport.OCI_ARCHIVE:
            # Throw before building.
            raise ArtifactRejected(
                transport = requirement.transport.value,
                reference = requirement.reference,
                detail = "OCI archives are not implemented by the Docker builder.",
            )
