"""Verify the SDK-backed `guide` command."""

# Imports.
from __future__ import annotations

from sdk_fixtures import FunctionClientFactory

from pathlib import Path

from click.testing import CliRunner, Result

# Import the CLI group and context.
from sandbox.cli.context import CliContext
from sandbox.cli.group import cli

# Import the public SDK.
from sandbox.sdk import SandboxClient

# Declare the preserved guide output exactly as Click renders it on a pipe.
EXPECTED_GUIDE: tuple[str, ...] = (
    '`sandbox` or `sb` is a tool for managing isolated development environments.',
    '',
    'Details',
    '',
    '`sandbox` is designed around the following main concepts:',
    '',
    '  ∙ A box is a `docker`-based development environment associated with a local',
    '  project directory. Boxes provide isolated execution environments for',
    '  development tools and agents while retaining access to explicitly mounted',
    '  resources.',
    '',
    '  ∙ A catalogue is a collection of reusable development recipes.',
    '',
    '  ∙ A recipe defines the `docker` configuration needed to provision a',
    '  particular type of environment, such as a base Ubuntu environment or an R',
    '  environment.',
    '',
    '  ∙ A volume is persistent `docker`-managed storage that can be shared between',
    '  boxes and survives container removal.',
    '',
    '  ∙ A secret is a user-owned file on the host that is mounted into a box.',
    '  Secrets are declared by recipes and bound to host paths by the user.',
    '',
    'Getting Started',
    '',
    '  # Create a catalogue named `my-catalogue`.',
    '  # Select the `base` catalogue from the public catalogue repository.',
    '  sb create catalogue my-catalogue \\',
    '      --source https://github.com/mihaiconstantin/sandbox-catalogues.git \\',
    '      --which base',
    '',
    '  # Create a box for the project `my-project`.',
    '  # Use the default recipe from `my-catalogue`.',
    '  sb create box my-project \\',
    '      --project-dir ~/Repositories/my-project \\',
    '      --catalogue my-catalogue',
    '',
    '  # Enter the box for the project `my-project`.',
    '  sb enter my-project',
    '',
    'Managing Catalogues',
    '',
    '  # List all registered catalogues.',
    '  sb list catalogues',
    '',
    '  # Edit the registered catalogue `my-catalogue`.',
    '  sb edit catalogue my-catalogue',
    '',
    '  # Remove the registered catalogue `my-catalogue`.',
    '  sb remove catalogue my-catalogue',
    '',
    'Managing Boxes',
    '',
    '  # List all available boxes.',
    '  sb list boxes',
    '',
    '  # Show the status of the box for the project `my-project`.',
    '  sb status my-project',
    '',
    '  # Start the box for the project `my-project`.',
    '  sb start my-project',
    '',
    '  # Stop the box for the project `my-project`.',
    '  sb stop my-project',
    '',
    '  # Remove the box for the project `my-project`.',
    '  sb remove box my-project',
    '',
    'Managing Volumes',
    '',
    '  # Create a volume named `my-volume`.',
    '  sb create volume my-volume',
    '',
    '  # List all available volumes.',
    '  sb list volumes',
    '',
    '  # Remove the volume named `my-volume`.',
    '  sb remove volume my-volume',
    '',
    'Managing Secrets',
    '',
    '  # Set the secret `example-secret` to the file `~/.keys/example-secret`.',
    '  sb create secret example-secret \\',
    '      --file ~/.keys/example-secret \\',
    '      --catalogue team',
    '',
    '  # List all available secrets.',
    '  sb list secrets',
    '',
    '  # Remove the secret `example-secret`.',
    '  sb remove secret example-secret --catalogue team',
    '',
    'More Information',
    '',
    'Run `sb <command> --help` for command-specific options and usage.',
)

# Declare the preserved section headings in display order.
EXPECTED_HEADINGS: tuple[str, ...] = (
    "Details",
    "Getting Started",
    "Managing Catalogues",
    "Managing Boxes",
    "Managing Volumes",
    "Managing Secrets",
    "More Information",
)


# Build a context whose client factory fails on any eager probe.
def inert_context() -> CliContext:
    # Fail when any command constructs a client.
    def fail(_home: Path) -> SandboxClient:
        # Throw a programming failure for an eager probe.
        raise AssertionError("guide must not construct a client.")

    # Return the inert identity.
    return CliContext(client_factory = FunctionClientFactory(fail))


# Invoke the complete command tree with the inert context.
def invoke(args: list[str]) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = inert_context(), prog_name = "sandbox")


# Verify the guide prints its preserved fixed text, headings, and wrapping.
def test_guide_preserves_the_fixed_text_and_wrapping() -> None:
    # Print the guide without invoking a client or probe.
    result: Result = invoke(["guide"])

    # Require the exact compatibility output on stdout and nothing on stderr.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "\n".join(EXPECTED_GUIDE) + "\n"
    assert result.stderr == ""

    # Require the headings in their preserved order.
    positions: list[int] = [result.stdout.index(heading) for heading in EXPECTED_HEADINGS]
    assert positions == sorted(positions)

    # Require plain output with no ANSI escapes and wrapped prose.
    assert "\x1b" not in result.stdout
    assert max(len(line) for line in result.stdout.splitlines()) <= 80
    assert "  sb create box my-project \\\n      --project-dir ~/Repositories/my-project \\\n      --catalogue my-catalogue\n" in result.stdout
    assert "  sb create secret example-secret \\\n      --file ~/.keys/example-secret \\\n      --catalogue team\n" in result.stdout


# Verify guide help and the root epilog keep their preserved references.
def test_guide_help_and_root_epilog_reference_guide() -> None:
    # Require the command help without constructing a client.
    help_result: Result = invoke(["guide", "--help"])
    assert help_result.exit_code == 0, help_result.stderr
    assert "Print a guide for getting started with `sandbox`." in help_result.stdout
    assert help_result.stderr == ""

    # Require the root help epilog to keep pointing at the guide.
    root_help: Result = invoke(["--help"])
    assert root_help.exit_code == 0, root_help.stderr
    assert "Run `sb guide` for getting started." in root_help.stdout
    assert "guide" in root_help.stdout
    assert root_help.stderr == ""


# Verify the undocumented create alias still resolves on the new root.
def test_create_catalog_alias_still_resolves() -> None:
    # Resolve the alias without invoking any command body.
    result: Result = invoke(["create", "catalog", "--help"])

    # Require the canonical catalogue command help.
    assert result.exit_code == 0, result.stderr
    assert "Install a `sandbox` catalogue of development recipes." in result.stdout
    assert result.stderr == ""


# Allow the focused tests to run directly.
if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
