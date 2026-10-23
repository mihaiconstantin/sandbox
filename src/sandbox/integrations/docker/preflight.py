# Imports.
from __future__ import annotations

import re

# Import the public prerequisite failure.
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Import the gateways used by the preflight probes.
from sandbox.integrations.docker.cli import DockerCli
from sandbox.integrations.docker.command import CommandResult
from sandbox.integrations.docker.compose_cli import ComposeCli
from sandbox.integrations.docker.invocation import buildx_version_arguments

# Declare the supported host-tool floors.
COMPOSE_MINIMUM: str = "5.6.0"
BUILDX_MINIMUM: str = "0.17.0"

# Match the first semantic version in a tool banner.
_VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")
