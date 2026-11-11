"""Verify the SDK-backed catalogue and secret commands."""

# Imports.
from __future__ import annotations

from sdk_fixtures import FunctionClientFactory

import io
import os
import shutil
import tomllib
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest import mock

import click
import pytest
from click.testing import CliRunner, Result
from rich.console import Console

# Import the CLI group and context.
from sandbox.cli.context import CliContext
from sandbox.cli.group import cli
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary

# Import the public SDK and fake ports.
from sandbox.sdk import SandboxClient
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime

# Import test fixtures.
from git_fixtures import GIT_AVAILABLE, GIT_ENVIRONMENT, make_git_repository

# Define the Docker-compatible vocabulary used by composition in production.
DOCKER_VOCABULARY: RuntimeVocabulary = RuntimeVocabulary(
    backend = "docker",
    title = "Container",
    tool = "`docker`",
    noun = "container",
    plural = "containers",
)

# Locate the bundled catalogue used as local and `git` source content.
BUNDLED_CATALOGUE: Path = Path(__file__).resolve().parents[1] / "catalogues" / "default"


# Build a pipe-safe presentation for command tests.
def make_presentation(*, tty: bool = False) -> tuple[CliPresentation, io.StringIO]:
    # Capture the stderr console separately from Click streams.
    buffer = io.StringIO()

    # Construct a deterministic console without markup or color.
    console = Console(
        file = buffer,
        force_terminal = tty,
        force_interactive = tty,
        color_system = None,
        width = 80,
        markup = False,
        emoji = False,
        highlight = False,
    )

    # Return the presentation and its captured stream.
    return CliPresentation(err = console, is_terminal = tty), buffer


# Build one injected context over a real client with fake ports.
def make_context(*, tty: bool = False) -> tuple[CliContext, list[tuple[Path, object]], io.StringIO]:
    # Capture the presentation and record client bindings.
    presentation, buffer = make_presentation(tty = tty)
    calls: list[tuple[Path, object]] = []

    # Build one client per requested home with the presentation sink.
    def factory(home: Path) -> SandboxClient:
        # Record the home and output sink.
        calls.append((home, presentation.output))

        # Construct the inert public client over the fake ports.
        return SandboxClient(home = home, runtime = FakeRuntime(), builder = FakeBuilder(), output = presentation.output)

    # Build the injected CLI context with a Click-owned error presenter.
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Return the context, recorded bindings, and transient stream.
    return context, calls, buffer


# Invoke the complete command tree with the injected context.
def invoke(args: list[str], context: CliContext, *, input: str | None = None, env: dict[str, str] | None = None) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = context, input = input, env = env, prog_name = "sandbox")


# Create one registered catalogue with a valid manifest and compose file.
def make_catalogue(home: Path, name: str = "default", *, recipes: tuple[str, ...] = ("base",), default: str | None = "base") -> Path:
    # Create the canonical catalogue directory.
    directory: Path = home / "catalogues" / name
    directory.mkdir(parents = True)

    # Build the catalogue and recipe declarations.
    default_line: str = f'default_recipe = "{default}"\n' if default is not None else ""
    recipe_blocks: str = "\n".join(
        dedent(f"""\
            [recipes.{recipe}]
            compose = "compose.yaml"
            service = "workspace"
        """)
        for recipe in recipes
    )
    (directory / "catalogue.toml").write_text(
        f'[catalogue]\nname = "{name}"\nversion = "0.1.0"\nschema_version = 1\n{default_line}\n{recipe_blocks}',
        encoding = "utf-8",
    )
    (directory / "compose.yaml").write_text("services: {}\n", encoding = "utf-8")

    # Register the catalogue at its canonical managed path.
    (home / "catalogues.toml").write_text(
        f'[catalogues.{name}]\ntype = "bundled"\npath = "catalogues/{name}"\n',
        encoding = "utf-8",
    )

    # Return the catalogue directory.
    return directory


# Read one TOML file for structural assertions.
def read_toml(path: Path) -> dict[str, Any]:
    # Parse the file.
    return tomllib.loads(path.read_text(encoding = "utf-8"))


# Verify bundled and local sources install through the SDK with current messages.
def test_create_catalogue_installs_bundled_and_local_sources(tmp_path: Path) -> None:
    # Prepare an absent home so installation creates it.
    home: Path = tmp_path / "home"
    context, calls, buffer = make_context()

    # Install the bundled catalogue under a custom name.
    bundled: Result = invoke(["create", "catalogue", "team", "--home", str(home)], context)
    assert bundled.exit_code == 0, bundled.stderr
    assert bundled.stderr == ""
    assert buffer.getvalue() == ""
    installed: Path = home.resolve() / "catalogues" / "team"
    assert (installed / "catalogue.toml").is_file()
    assert "Installing catalogue `team`...\n" in bundled.stdout
    assert f"Successfully installed catalogue `team` at `{installed}`.\n" in bundled.stdout
    assert read_toml(home / "catalogues.toml")["catalogues"]["team"] == {"type": "bundled", "path": "catalogues/team"}

    # Install a local source under a second name and preserve the source.
    source: Path = tmp_path / "source"
    shutil.copytree(BUNDLED_CATALOGUE, source)
    before: str = (source / "catalogue.toml").read_text(encoding = "utf-8")
    local: Result = invoke(["create", "catalogue", "local", "--source", str(source), "--home", str(home)], context)
    assert local.exit_code == 0, local.stderr
    assert (home.resolve() / "catalogues" / "local" / "catalogue.toml").is_file()
    assert (source / "catalogue.toml").read_text(encoding = "utf-8") == before
    assert "Successfully installed catalogue `local`" in local.stdout
    assert read_toml(home / "catalogues.toml")["catalogues"]["local"] == {"type": "local", "path": "catalogues/local"}

    # Require both operations to bind the selected home and presentation sink.
    assert calls == [(home, calls[0][1]), (home, calls[1][1])]


# Verify a `git` source installs and registers its origin.
@pytest.mark.skipif(not GIT_AVAILABLE, reason = "`git` is not available.")
def test_create_catalogue_installs_a_git_source(tmp_path: Path) -> None:
    # Prepare a home and an offline repository.
    home: Path = tmp_path / "home"
    repository: Path = make_git_repository(tmp_path)
    context, _calls, _buffer = make_context()

    # Install the repository under isolated `git` configuration.
    with mock.patch.dict(os.environ, GIT_ENVIRONMENT):
        result: Result = invoke(["create", "catalogue", "team", "--source", repository.as_uri(), "--home", str(home)], context)

    # Require the retained repository, rewritten manifest, and registration.
    assert result.exit_code == 0, result.stderr
    installed: Path = home.resolve() / "catalogues" / "team"
    assert (installed / ".git" / "HEAD").is_file()
    assert (installed / "catalogue.toml").is_file()
    assert read_toml(home / "catalogues.toml")["catalogues"]["team"] == {"type": "git", "path": "catalogues/team"}


# Verify forced replacement warns, confirms, and honors `--yes`.
def test_create_catalogue_force_confirmation_and_yes(tmp_path: Path) -> None:
    # Install the catalogue first and add a stale marker.
    home: Path = tmp_path / "home"
    context, _calls, _buffer = make_context()
    first: Result = invoke(["create", "catalogue", "team", "--home", str(home)], context)
    assert first.exit_code == 0, first.stderr
    installed: Path = home.resolve() / "catalogues" / "team"
    marker: Path = installed / "marker.txt"
    marker.write_text("original catalogue", encoding = "utf-8")
    registry_before: str = (home / "catalogues.toml").read_text(encoding = "utf-8")

    # Decline the forced replacement.
    declined: Result = invoke(["create", "catalogue", "team", "--force", "--home", str(home)], context, input = "n\n")
    assert declined.exit_code == 1
    assert "Existing catalogue files and local modifications will be replaced.\n" in declined.stdout
    assert "Are you sure you want to replace the existing catalogue?" in declined.stdout
    assert "Aborted!" in declined.stderr
    assert marker.read_text(encoding = "utf-8") == "original catalogue"
    assert (home / "catalogues.toml").read_text(encoding = "utf-8") == registry_before

    # Replace without confirmation when `--yes` is explicit.
    replaced: Result = invoke(["create", "catalogue", "team", "--force", "--yes", "--home", str(home)], context)
    assert replaced.exit_code == 0, replaced.stderr
    assert "Are you sure you want to replace the existing catalogue?" not in replaced.stdout
    assert "Existing catalogue files and local modifications will be replaced." not in replaced.stdout
    assert not marker.exists()


# Verify an existing catalogue still requires `--force` and `--yes` never bypasses it.
def test_create_catalogue_requires_force_to_replace(tmp_path: Path) -> None:
    # Install the catalogue first.
    home: Path = tmp_path / "home"
    context, _calls, _buffer = make_context()
    assert invoke(["create", "catalogue", "team", "--home", str(home)], context).exit_code == 0

    # Request replacement without `--force`.
    result: Result = invoke(["create", "catalogue", "team", "--yes", "--home", str(home)], context)

    # Require the installer refusal without a prompt.
    assert result.exit_code == 1
    assert "Use `--force` to replace it" in result.stderr
    assert "Are you sure you want to replace the existing catalogue?" not in result.stdout


# Verify invalid names are Click usage errors and invalid manifests are presented plainly.
def test_create_catalogue_validation_and_manifest_failure(tmp_path: Path) -> None:
    # Reject an invalid identifier before constructing a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("validation must not construct a client")

    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    for name in ("Bad", "../team"):
        result: Result = invoke(["create", "catalogue", name, "--home", str(tmp_path / "home")], context)
        assert result.exit_code == 2
        assert "Invalid value for 'NAME'" in result.stderr
        assert "Must start with a lowercase letter or digit" in result.stderr
        assert not (tmp_path / "home").exists()

    # Reject a local source with a malformed manifest without publishing it.
    source: Path = tmp_path / "broken"
    source.mkdir()
    (source / "catalogue.toml").write_text("[catalogue\n", encoding = "utf-8")
    home: Path = tmp_path / "home"
    flow_context, _calls, _buffer = make_context()
    result = invoke(["create", "catalogue", "broken", "--source", str(source), "--home", str(home)], flow_context)
    assert result.exit_code == 1
    assert result.stdout == "Installing catalogue `broken`...\n"
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr
    assert not (home.resolve() / "catalogues" / "broken").exists()
    assert not (home / "catalogues.toml").exists()


# Verify the editor opens the managed directory and validation runs afterwards.
def test_edit_catalogue_opens_the_editor_and_validates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = make_catalogue(home, "team")
    context, calls, buffer = make_context()
    opened: list[Path] = []

    # Replace the editor with a blocking no-op that records its target.
    def editor(*, filename: Path) -> None:
        opened.append(filename)

    monkeypatch.setattr(click, "edit", editor)

    # Edit the catalogue.
    result: Result = invoke(["edit", "catalogue", "team", "--home", str(home)], context)

    # Require the managed path, replacement warning, and validation result.
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    assert opened == [directory]
    assert f"Editing catalogue `team` at `{directory}`.\n" in result.stdout
    assert "Reinstalling this catalogue with `--force` replaces local changes.\n" in result.stdout
    assert "Catalogue `team` is valid.\n" in result.stdout
    assert calls[0][0] == home


# Verify an invalid edited catalogue and a missing registration are plain errors.
def test_edit_catalogue_reports_invalid_and_missing_catalogues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = make_catalogue(home, "team")
    context, _calls, _buffer = make_context()

    # Corrupt the manifest from the editor.
    def corrupt(*, filename: Path) -> None:
        (filename / "catalogue.toml").write_text("[catalogue\n", encoding = "utf-8")

    monkeypatch.setattr(click, "edit", corrupt)
    invalid: Result = invoke(["edit", "catalogue", "team", "--home", str(home)], context)
    assert invalid.exit_code == 1
    assert invalid.stdout.startswith("Editing catalogue `team`")
    assert invalid.stderr.startswith("Error: ")
    assert "not valid TOML" in invalid.stderr
    assert (directory / "catalogue.toml").read_text(encoding = "utf-8") == "[catalogue\n"

    # Request an unregistered catalogue without opening the editor.
    opened: list[Path] = []
    monkeypatch.setattr(click, "edit", lambda *, filename: opened.append(filename))
    missing: Result = invoke(["edit", "catalogue", "missing", "--home", str(home)], context)
    assert missing.exit_code == 1
    assert missing.stdout == ""
    assert "Catalogue `missing` is not registered" in missing.stderr
    assert "Run `sb list catalogues` to see registered catalogues." in missing.stderr
    assert opened == []


# Verify list catalogues renders the compatibility table and empty state.
def test_list_catalogues_table_and_empty_state(tmp_path: Path) -> None:
    # Register two catalogues out of alphabetical order.
    home: Path = tmp_path / "home"
    home.mkdir()
    (home / "catalogues.toml").write_text(
        '[catalogues.zeta]\ntype = "local"\npath = "catalogues/zeta"\n\n'
        '[catalogues.alpha]\ntype = "bundled"\npath = "catalogues/alpha"\n',
        encoding = "utf-8",
    )
    context, _calls, buffer = make_context()

    # Render the registrations.
    result: Result = invoke(["list", "catalogues", "--home", str(home)], context)
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    lines: list[str] = result.stdout.rstrip("\n").splitlines()
    assert lines[0].split() == ["NAME", "TYPE", "PATH"]
    assert [line.split()[:2] for line in lines[1:]] == [["alpha", "bundled"], ["zeta", "local"]]
    assert str(home / "catalogues" / "alpha") in lines[1]

    # Report the empty state without requiring a home directory.
    missing_home: Path = tmp_path / "missing"
    empty: Result = invoke(["list", "catalogues", "--home", str(missing_home)], context)
    assert empty.exit_code == 0
    assert empty.stdout == "No catalogues registered.\n"
    assert empty.stderr == ""


# Verify list recipes renders sorted recipes with the default marker.
def test_list_recipes_table_and_validation(tmp_path: Path) -> None:
    # Prepare a catalogue with out-of-order recipes and a declared default.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "team", recipes = ("zeta", "base", "r"), default = "r")
    context, _calls, buffer = make_context()

    # Render the recipes.
    result: Result = invoke(["list", "recipes", "--catalogue", "team", "--home", str(home)], context)
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    lines: list[str] = result.stdout.rstrip("\n").splitlines()
    assert lines[0].split() == ["NAME", "DEFAULT"]
    assert [line.split() for line in lines[1:]] == [["base"], ["r", "yes"], ["zeta"]]

    # Reject an invalid catalogue option before constructing a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("validation must not construct a client")

    presentation, _buffer = make_presentation()
    usage_context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    usage: Result = invoke(["list", "recipes", "--catalogue", "Bad", "--home", str(home)], usage_context)
    assert usage.exit_code == 2
    assert "Invalid value for '-c' / '--catalogue'" in usage.stderr
    assert "Must start with a lowercase letter or digit" in usage.stderr

    # Report an unregistered catalogue through the single presenter.
    missing: Result = invoke(["list", "recipes", "--catalogue", "missing", "--home", str(home)], context)
    assert missing.exit_code == 1
    assert missing.stdout == ""
    assert "Error: Catalogue `missing` is not registered" in missing.stderr


# Verify malformed registries and invalid manifests are presented cleanly.
def test_list_catalogues_reports_malformed_configuration(tmp_path: Path) -> None:
    # Prepare a malformed registry.
    home: Path = tmp_path / "home"
    home.mkdir()
    (home / "catalogues.toml").write_text("[catalogues\n", encoding = "utf-8")
    context, _calls, _buffer = make_context()

    # Require the malformed registry to be a plain failure.
    result: Result = invoke(["list", "catalogues", "--home", str(home)], context)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr

    # Prepare a valid registry with a non-UTF-8 registry file.
    (home / "catalogues.toml").write_bytes(b"\xff\xfe")
    invalid_encoding: Result = invoke(["list", "catalogues", "--home", str(home)], context)
    assert invalid_encoding.exit_code == 1
    assert invalid_encoding.stderr.startswith("Error: ")
    assert "Traceback" not in invalid_encoding.stderr


# Verify an invalid catalogue manifest is a plain error for recipe listing.
def test_list_recipes_reports_an_invalid_manifest(tmp_path: Path) -> None:
    # Prepare a registered catalogue with an invalid manifest.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = make_catalogue(home, "team")
    (directory / "catalogue.toml").write_text("[catalogue\n", encoding = "utf-8")
    context, _calls, _buffer = make_context()

    # Require the manifest failure to be plain and attributable.
    result: Result = invoke(["list", "recipes", "--catalogue", "team", "--home", str(home)], context)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Error: ")
    assert "not valid TOML" in result.stderr
    assert "Traceback" not in result.stderr


# Verify a missing local catalogue source is a plain installation failure.
def test_create_catalogue_reports_a_missing_local_source(tmp_path: Path) -> None:
    # Request a local source that does not exist.
    home: Path = tmp_path / "home"
    context, _calls, _buffer = make_context()
    result: Result = invoke(["create", "catalogue", "team", "--source", str(tmp_path / "missing"), "--home", str(home)], context)

    # Require the installation error without any partial publication.
    assert result.exit_code == 1
    assert result.stdout == "Installing catalogue `team`...\n"
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr
    assert not (home.resolve() / "catalogues" / "team").exists()
    assert not (home / "catalogues.toml").exists()


# Verify removal plans, confirms, displays bindings, and deletes the catalogue.
def test_remove_catalogue_plan_confirmation_and_removal(tmp_path: Path) -> None:
    # Prepare a registered catalogue with a catalogue-scoped secret binding.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = make_catalogue(home, "team")
    secret_file: Path = home / "keys" / "api_key"
    secret_file.parent.mkdir()
    secret_file.write_text("never displayed\n", encoding = "utf-8")
    (home / "catalogues.toml").write_text(
        (home / "catalogues.toml").read_text(encoding = "utf-8") + f'\n[secrets.team]\napi_key = {{ file = "{secret_file}" }}\n',
        encoding = "utf-8",
    )
    context, _calls, buffer = make_context()

    # Confirm the removal interactively.
    result: Result = invoke(["remove", "catalogue", "team", "--home", str(home)], context, input = "y\n")

    # Require the plan, warning, success message, and separate streams.
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    assert "Removing catalogue `team`..." in result.stdout
    assert "Catalogue\n" in result.stdout
    assert "  Name       team\n" in result.stdout
    assert "  Type       bundled\n" in result.stdout
    assert "  api_key -> " in result.stdout
    assert "  will be deleted\n" in result.stdout
    assert "The catalogue directory and any local modifications will be permanently deleted.\n" in result.stdout
    assert "Are you sure you want to remove this catalogue?" in result.stdout
    assert "Successfully removed catalogue `team`.\n" in result.stdout
    assert "never displayed" not in result.stdout

    # Require the files, registration, and bindings to be removed.
    assert not directory.exists()
    configuration: dict[str, Any] = read_toml(home / "catalogues.toml")
    assert "catalogues" not in configuration
    assert "secrets" not in configuration


# Verify declining confirmation aborts and an absent catalogue is skipped.
def test_remove_catalogue_declined_and_absent(tmp_path: Path) -> None:
    # Prepare a registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = make_catalogue(home, "team")
    registry_before: str = (home / "catalogues.toml").read_text(encoding = "utf-8")
    context, _calls, _buffer = make_context()

    # Decline the confirmation.
    declined: Result = invoke(["remove", "catalogue", "team", "--home", str(home)], context, input = "n\n")
    assert declined.exit_code == 1
    assert "Are you sure you want to remove this catalogue?" in declined.stdout
    assert "Aborted!" in declined.stderr
    assert directory.exists()
    assert (home / "catalogues.toml").read_text(encoding = "utf-8") == registry_before

    # Skip an unregistered catalogue without prompting.
    absent: Result = invoke(["remove", "catalogue", "missing", "--yes", "--home", str(home)], context)
    assert absent.exit_code == 0
    assert absent.stdout == "Skipped removing catalogue `missing` because it is not registered.\n"
    assert absent.stderr == ""


# Verify noncanonical registrations are refused and invalid names are usage errors.
def test_remove_catalogue_refuses_noncanonical_and_invalid_names(tmp_path: Path) -> None:
    # Prepare a registration outside the managed catalogue root.
    home: Path = tmp_path / "home"
    home.mkdir()
    (home / "catalogues.toml").write_text('[catalogues.vendor]\ntype = "local"\npath = "external/vendor"\n', encoding = "utf-8")
    vendor: Path = home / "external" / "vendor"
    vendor.mkdir(parents = True)
    registry_before: str = (home / "catalogues.toml").read_text(encoding = "utf-8")
    context, _calls, _buffer = make_context()

    # Attempt the removal without prompting.
    result: Result = invoke(["remove", "catalogue", "vendor", "--yes", "--home", str(home)], context)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "noncanonical path" in result.stderr
    assert vendor.exists()
    assert (home / "catalogues.toml").read_text(encoding = "utf-8") == registry_before

    # Reject an invalid name before constructing a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("validation must not construct a client")

    presentation, _buffer = make_presentation()
    usage_context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    usage: Result = invoke(["remove", "catalogue", "../team", "--yes", "--home", str(home)], usage_context)
    assert usage.exit_code == 2
    assert "Invalid value for 'NAME'" in usage.stderr


# Verify secret binding stores only the host path and never displays contents.
def test_create_secret_saves_binding_without_reading_content(tmp_path: Path) -> None:
    # Prepare a registered catalogue and a host secret file.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    secret_file: Path = tmp_path / "keys" / "example-secret"
    secret_file.parent.mkdir()
    secret_file.write_text("super-secret-value\n", encoding = "utf-8")
    context, _calls, buffer = make_context()

    # Bind the secret.
    result: Result = invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "default", "--home", str(home)],
        context,
    )

    # Require the saved binding, mount path, and clean streams.
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    assert f"Saved secret `example-secret` in catalogue `default` from `{secret_file.resolve()}`.\n" in result.stdout
    assert "Mounted read-only at `/run/secrets/example-secret`.\n" in result.stdout
    assert "super-secret-value" not in result.stdout
    configuration: dict[str, Any] = read_toml(home / "catalogues.toml")
    assert configuration["secrets"]["default"]["example-secret"]["file"] == str(secret_file.resolve())
    assert secret_file.read_text(encoding = "utf-8") == "super-secret-value\n"


# Verify unknown catalogues, missing files, and invalid identifiers keep their classes.
def test_create_secret_failures_and_validation(tmp_path: Path) -> None:
    # Prepare a registered catalogue and a host secret file.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    secret_file: Path = tmp_path / "example-secret"
    secret_file.write_text("value\n", encoding = "utf-8")
    context, _calls, _buffer = make_context()

    # Reject an unregistered catalogue with the discovery hint.
    unknown: Result = invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "other", "--home", str(home)],
        context,
    )
    assert unknown.exit_code == 1
    assert unknown.stdout == ""
    assert "Catalogue `other` is not registered" in unknown.stderr
    assert "Run `sb list catalogues` to see registered catalogues." in unknown.stderr

    # Reject a missing host file without reading or displaying it.
    missing: Result = invoke(
        ["create", "secret", "example-secret", "--file", str(tmp_path / "missing"), "--catalogue", "default", "--home", str(home)],
        context,
    )
    assert missing.exit_code == 1
    assert "does not exist" in missing.stderr
    assert "value" not in missing.stderr

    # Reject invalid catalogue and secret identifiers before constructing a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("validation must not construct a client")

    presentation, _buffer = make_presentation()
    usage_context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    cases: tuple[tuple[list[str], str], ...] = (
        (["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "Bad", "--home", str(home)], "Invalid value for '-c' / '--catalogue'"),
        (["create", "secret", "Bad", "--file", str(secret_file), "--catalogue", "default", "--home", str(home)], "Invalid value for 'SECRET'"),
    )
    for args, expected in cases:
        usage: Result = invoke(args, usage_context)
        assert usage.exit_code == 2
        assert expected in usage.stderr
        assert "Must start with a lowercase letter or digit" in usage.stderr

    # Require the catalogue option and an existing home.
    missing_option: Result = invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--home", str(home)],
        usage_context,
    )
    assert missing_option.exit_code == 2
    assert "Missing option '-c' / '--catalogue'" in missing_option.stderr
    missing_home: Result = invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "default", "--home", str(tmp_path / "absent")],
        usage_context,
    )
    assert missing_home.exit_code == 2
    assert "does not exist" in missing_home.stderr


# Verify list secrets renders bindings without contents and reports the empty state.
def test_list_secrets_table_and_empty_state(tmp_path: Path) -> None:
    # Prepare a registered catalogue and bind one secret through the CLI.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    secret_file: Path = tmp_path / "example-secret"
    secret_file.write_text("hidden-value\n", encoding = "utf-8")
    context, _calls, buffer = make_context()
    assert invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "default", "--home", str(home)],
        context,
    ).exit_code == 0

    # Render the binding.
    result: Result = invoke(["list", "secrets", "--home", str(home)], context)
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert buffer.getvalue() == ""
    lines: list[str] = result.stdout.rstrip("\n").splitlines()
    assert lines[0].split() == ["CATALOGUE", "SECRET", "HOST", "PATH", "BOX", "PATH"]
    assert lines[1].split() == ["default", "example-secret", str(secret_file.resolve()), "/run/secrets/example-secret"]
    assert "hidden-value" not in result.stdout
    assert "Mount paths are only relevant to boxes whose recipe declares the secret." in result.stdout
    assert "Run `sb status <project>` to inspect a box's actual mounts." in result.stdout

    # Report the empty state for a home without bindings.
    empty_home: Path = tmp_path / "empty"
    empty_home.mkdir()
    (empty_home / "catalogues.toml").write_text("", encoding = "utf-8")
    empty: Result = invoke(["list", "secrets", "--home", str(empty_home)], context)
    assert empty.exit_code == 0
    assert empty.stdout == "No secrets configured.\n"
    assert empty.stderr == ""


# Verify removing a secret deletes only the binding and preserves the host file.
def test_remove_secret_preserves_the_host_file(tmp_path: Path) -> None:
    # Prepare a registered catalogue and a bound secret.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    secret_file: Path = tmp_path / "example-secret"
    secret_file.write_text("hidden-value\n", encoding = "utf-8")
    context, _calls, _buffer = make_context()
    assert invoke(
        ["create", "secret", "example-secret", "--file", str(secret_file), "--catalogue", "default", "--home", str(home)],
        context,
    ).exit_code == 0

    # Remove the binding.
    removed: Result = invoke(
        ["remove", "secret", "example-secret", "--catalogue", "default", "--home", str(home)],
        context,
    )
    assert removed.exit_code == 0, removed.stderr
    assert removed.stderr == ""
    assert removed.stdout == "Removed secret `example-secret` from catalogue `default`.\n"
    assert secret_file.read_text(encoding = "utf-8") == "hidden-value\n"
    assert "secrets" not in read_toml(home / "catalogues.toml")

    # Report an absent binding without changing the host file.
    absent: Result = invoke(
        ["remove", "secret", "example-secret", "--catalogue", "default", "--home", str(home)],
        context,
    )
    assert absent.exit_code == 0
    assert absent.stdout == "No secret `example-secret` is configured in catalogue `default`.\n"
    assert secret_file.exists()


# Verify secret removal reports unknown catalogues and rejects invalid identifiers.
def test_remove_secret_failures_and_validation(tmp_path: Path) -> None:
    # Prepare a registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    context, _calls, _buffer = make_context()

    # Reject an unregistered catalogue with the discovery hint.
    unknown: Result = invoke(
        ["remove", "secret", "example-secret", "--catalogue", "other", "--home", str(home)],
        context,
    )
    assert unknown.exit_code == 1
    assert "Catalogue `other` is not registered" in unknown.stderr
    assert "Run `sb list catalogues` to see registered catalogues." in unknown.stderr

    # Reject invalid catalogue names and aliases before constructing a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("validation must not construct a client")

    presentation, _buffer = make_presentation()
    usage_context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    catalogue_usage: Result = invoke(
        ["remove", "secret", "example-secret", "--catalogue", "../default", "--home", str(home)],
        usage_context,
    )
    assert catalogue_usage.exit_code == 2
    assert "Invalid value for '-c' / '--catalogue'" in catalogue_usage.stderr
    alias_usage: Result = invoke(
        ["remove", "secret", "Bad", "--catalogue", "default", "--home", str(home)],
        usage_context,
    )
    assert alias_usage.exit_code == 2
    assert "Invalid value for 'SECRET'" in alias_usage.stderr


# Verify help and completion stay Click-owned and construct no client.
def test_catalogue_and_secret_help_constructs_no_client() -> None:
    # Fail the test if any help path constructs a client.
    def fail(_home: Path) -> SandboxClient:
        raise AssertionError("help/completion must not construct a client")

    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(fail))
    for args in (
        ["create", "catalogue", "--help"],
        ["edit", "catalogue", "--help"],
        ["list", "catalogues", "--help"],
        ["list", "recipes", "--help"],
        ["remove", "catalogue", "--help"],
        ["create", "secret", "--help"],
        ["list", "secrets", "--help"],
        ["remove", "secret", "--help"],
    ):
        result: Result = invoke(args, context)
        assert result.exit_code == 0, result.stderr
        assert "Usage:" in result.stdout
        assert result.stderr == ""


# Verify help and table output remain plain under a hostile pipe environment.
def test_catalogue_and_secret_output_is_plain_under_a_pipe(tmp_path: Path) -> None:
    # Prepare a catalogue registration.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "team")
    context, _calls, _buffer = make_context()
    hostile: dict[str, str] = {"FORCE_COLOR": "1", "TTY_COMPATIBLE": "1", "COLUMNS": "500", "TERM": "xterm-256color"}

    # Render the registrations and help with hostile color variables.
    listed: Result = invoke(["list", "catalogues", "--home", str(home)], context, env = hostile)
    assert listed.exit_code == 0, listed.stderr
    assert "\x1b" not in listed.stdout
    assert str(home / "catalogues" / "team") in listed.stdout

    helped: Result = invoke(["remove", "catalogue", "--help"], context, env = hostile)
    assert helped.exit_code == 0
    assert "\x1b" not in helped.stdout
    assert max(len(line) for line in helped.stdout.splitlines()) <= 80


# Verify the commands bind the selected home through the injected factory.
def test_catalogue_and_secret_commands_bind_the_selected_home(tmp_path: Path) -> None:
    # Prepare a home with a registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    make_catalogue(home, "default")
    context, calls, _buffer = make_context()

    # Run one read command and require the exact home and presentation sink.
    result: Result = invoke(["list", "catalogues", "--home", str(home)], context)
    assert result.exit_code == 0, result.stderr
    assert calls == [(home, context.presentation.output)]

    # Require a missing home for secret commands to remain a Click usage error.
    missing: Result = invoke(["list", "secrets", "--home", str(tmp_path / "absent")], context)
    assert missing.exit_code == 2
    assert "does not exist" in missing.stderr
    assert [path for path, _sink in calls] == [home]


# Allow the focused tests to run directly.
if __name__ == "__main__":
    # Run pytest for this file.
    raise SystemExit(pytest.main([__file__]))
