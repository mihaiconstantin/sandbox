"""Verify the create group preserves the undocumented catalogue alias."""

# Imports.
from __future__ import annotations

import re

from click.testing import CliRunner, Result

# Import the root CLI group.
from sandbox.cli.group import cli


# Verify `create catalog` resolves to the canonical catalogue command.
def test_create_catalog_alias_resolves_to_catalogue_help() -> None:
    # Resolve the alias without invoking any command body.
    result: Result = CliRunner().invoke(cli, ["create", "catalog", "--help"])

    # Require the canonical command help.
    assert result.exit_code == 0, result.output
    assert "Install a `sandbox` catalogue of development recipes." in result.output


# Verify the alias stays hidden from the command listing.
def test_create_alias_is_not_listed_as_a_command() -> None:
    # Read the create group help.
    result: Result = CliRunner().invoke(cli, ["create", "--help"])

    # Require a clean listing that does not advertise the compatibility alias.
    assert result.exit_code == 0, result.output
    assert "catalogue" in result.output
    assert re.search(r"\bcatalog\b", result.output) is None
