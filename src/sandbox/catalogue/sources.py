# Imports.
import os
import shutil
import signal
import subprocess
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

from sandbox.configuration import registry

# Import errors and helpers.
from sandbox.errors.catalogues import CatalogueInstallError
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Define the fixed timeout for cloning a `git` catalogue.
GIT_CLONE_TIMEOUT: int = 120

# Define the supported `git` URL schemes.
GIT_URL_SCHEMES: frozenset[str] = frozenset({"https", "http", "ssh", "git", "file"})
