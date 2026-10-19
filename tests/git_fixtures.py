# Imports.
import os
import shutil
import subprocess
from pathlib import Path

# Locate the bundled catalogue used as repository content.
CATALOGUE_DIRECTORY: Path = Path(__file__).resolve().parents[1] / "catalogues" / "default"

# Report whether the `git` executable is available.
GIT_AVAILABLE: bool = shutil.which("git") is not None

# Isolate `git` configuration and allow the file protocol for offline tests.
GIT_ENVIRONMENT: dict[str, str] = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
    "GIT_ALLOW_PROTOCOL": "file",
}


# Create an offline `git` repository containing the bundled catalogue.
def make_git_repository(root: Path) -> Path:
    # Copy the bundled catalogue into the repository.
    repository: Path = root / "repository"
    shutil.copytree(CATALOGUE_DIRECTORY, repository)

    # Initialize the repository and commit the catalogue without signing or line-ending conversion.
    commands: tuple[list[str], ...] = (
        ["git", "init", "--quiet"],
        ["git", "-c", "core.autocrlf=false", "add", "."],
        ["git", "-c", "user.name=Sandbox Test", "-c", "user.email=sandbox@example.com", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", "commit", "--quiet", "-m", "Initial catalogue."],
    )
    environment: dict[str, str] = {**os.environ, **GIT_ENVIRONMENT}
    for command in commands:
        subprocess.run(command, cwd = repository, check = True, capture_output = True, text = True, env = environment)

    # Return the repository directory.
    return repository
