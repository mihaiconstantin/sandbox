"""Verify the SDK-backed create and remove volume commands."""

# Imports.
from __future__ import annotations

from sdk_fixtures import FunctionClientFactory

import io
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rich.console import Console

# Import the CLI group and context.
from sandbox.cli.context import CliContext
from sandbox.cli.group import cli
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.text import strip_ansi
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary

# Import the public SDK and fake ports.
from sandbox.sdk import SandboxClient
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime

# Import the domain values used to seed volumes.
from sandbox.domain import RuntimeRef

# Import the typed volume and removal failures.
from sandbox.errors.base import CommandFailure
from sandbox.errors.engine import EngineFailure
from sandbox.errors.removal import IncompleteRemoval
from sandbox.errors.volumes import VolumeOwnershipError

# Define the Docker-compatible vocabulary used by composition in production.
DOCKER_VOCABULARY: RuntimeVocabulary = RuntimeVocabulary(
    backend = "docker",
    title = "Container",
    tool = "`docker`",
    noun = "container",
    plural = "containers",
)


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
def make_context(runtime: FakeRuntime, *, tty: bool = False) -> tuple[CliContext, list[tuple[Path, object]], io.StringIO]:
    # Capture the presentation and record client bindings.
    presentation, buffer = make_presentation(tty = tty)
    calls: list[tuple[Path, object]] = []

    # Build one client per requested home with the presentation sink.
    def factory(home: Path) -> SandboxClient:
        # Record the home and output sink.
        calls.append((home, presentation.output))

        # Construct the inert public client over the fake ports.
        return SandboxClient(home = home, runtime = runtime, builder = FakeBuilder(), output = presentation.output)

    # Build the injected CLI context with a Click-owned error presenter.
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Return the context, recorded bindings, and transient stream.
    return context, calls, buffer


# Invoke the complete command tree with the injected context.
def invoke(args: list[str], context: CliContext, *, input: str | None = None) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = context, input = input, prog_name = "sandbox")


# Verify creation reports success or the preserved skip without stdout prose.
def test_create_volume_reports_success_and_skip() -> None:
    # Create a missing volume through the SDK-backed command.
    runtime = FakeRuntime()
    context, calls, _buffer = make_context(runtime)
    result: Result = invoke(["create", "volume", "my-volume"], context)

    # Require the success result on stdout and no persistent stderr bytes.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Successfully created a `docker` volume named `my-volume`.\n"
    assert result.stderr == ""
    assert runtime.ensure_volume_requests == ["my-volume"]
    assert runtime.inspect_volume("my-volume") is not None
    assert [home for home, _sink in calls] == [Path.home() / ".sandbox"]

    # Create an existing volume and require the preserved skip message.
    existing_runtime = FakeRuntime()
    existing_runtime.add_volume("my-volume")
    existing_context, _calls, _buffer = make_context(existing_runtime)
    existing: Result = invoke(["create", "volume", "my-volume"], existing_context)

    # Require a successful no-op that reports the skip on stdout.
    assert existing.exit_code == 0, existing.stderr
    assert existing.stdout == "Skipped creating the `docker` volume `my-volume` because it already exists.\n"
    assert existing.stderr == ""
    assert existing_runtime.inspect_volume("my-volume") is not None


# Verify a creation engine failure keeps its command facts, status, and stream.
def test_create_volume_preserves_engine_failure_status_and_stderr() -> None:
    # Queue one structured volume-creation failure.
    runtime = FakeRuntime()
    runtime.fail_next(
        EngineFailure(
            CommandFailure(
                backend = "docker",
                operation = "volume.create",
                command = ("docker", "volume", "create", "my-volume"),
                exit_code = 125,
                diagnostic = "permission denied",
            ),
        ),
    )
    context, _calls, _buffer = make_context(runtime)
    result: Result = invoke(["create", "volume", "my-volume"], context)

    # Require the positive engine status and the single plain presenter on stderr.
    assert result.exit_code == 125
    assert result.stdout == ""
    assert result.stderr == "Error: `docker volume create my-volume` failed with exit code 125: permission denied.\n"


# Verify removal displays the preserved table, confirms, and verifies absence.
def test_remove_volume_displays_metadata_and_verifies_removal(tmp_path: Path) -> None:
    # Prepare a volume whose mountpoint contains external data.
    data_directory: Path = tmp_path / "volume-data"
    data_directory.mkdir()
    marker: Path = data_directory / "keep.txt"
    marker.write_text("external data\n", encoding = "utf-8")

    # Seed the managed volume and remove it without prompting.
    runtime = FakeRuntime()
    runtime.add_volume("shared", driver = "local", mountpoint = str(data_directory))
    context, _calls, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "volume", "shared", "--yes"], context)

    # Require the preserved metadata table, warning, and success message.
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert "Volume\n" in result.stdout
    assert "  Name       shared\n" in result.stdout
    assert "  Driver     local\n" in result.stdout
    assert f"  Mountpoint {data_directory}\n" in result.stdout
    assert "Referencing containers\n" in result.stdout
    assert "  None\n" in result.stdout
    assert "All data stored in this volume will be permanently deleted.\n" in result.stdout
    assert "Successfully removed the `docker` volume `shared`.\n" in result.stdout

    # Require the removal call, the absence proof, and untouched external data.
    assert runtime.remove_volume_requests == ["shared"]
    assert runtime.inspect_volume("shared") is None
    assert marker.read_text(encoding = "utf-8") == "external data\n"


# Verify a missing volume is skipped with the preserved message and success status.
def test_remove_volume_skips_an_absent_volume() -> None:
    # Attempt to remove a volume that does not exist.
    runtime = FakeRuntime()
    context, _calls, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "volume", "shared", "--yes"], context)

    # Require the skip message without a removal call.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Skipped removing the `docker` volume `shared` because it does not exist.\n"
    assert result.stderr == ""
    assert runtime.remove_volume_requests == []


# Verify removal refuses unmanaged, referenced, and reference-unknown volumes.
def test_remove_volume_refuses_unsafe_volumes() -> None:
    # Refuse a volume whose ownership cannot be verified.
    unmanaged_runtime = FakeRuntime()
    unmanaged_runtime.fail_next(VolumeOwnershipError("shared"))
    unmanaged_context, _calls, _buffer = make_context(unmanaged_runtime)
    unmanaged: Result = invoke(["remove", "volume", "shared", "--yes"], unmanaged_context)

    # Require the ownership refusal before any metadata is displayed.
    assert unmanaged.exit_code == 1
    assert unmanaged.stdout == ""
    assert unmanaged.stderr == "Error: Cannot verify `sandbox` ownership of volume `shared`.\n"
    assert unmanaged_runtime.remove_volume_requests == []

    # Refuse a volume still referenced by a container.
    referenced_runtime = FakeRuntime()
    referenced_runtime.add_volume("shared", in_use_by = (RuntimeRef(id = "cid", name = "demo-workspace-1"),))
    referenced_context, _calls, _buffer = make_context(referenced_runtime)
    referenced: Result = invoke(["remove", "volume", "shared", "--yes"], referenced_context)

    # Require the reference refusal that still names the container.
    assert referenced.exit_code == 1
    assert "  demo-workspace-1\n" in referenced.stdout
    assert referenced.stderr == "Error: Volume `shared` is still referenced by `docker` containers.\n"
    assert referenced_runtime.remove_volume_requests == []
    assert referenced_runtime.inspect_volume("shared") is not None

    # Refuse a volume whose reference set cannot be established.
    unknown_runtime = FakeRuntime()
    unknown_runtime.add_volume("shared", in_use_by = None)
    unknown_context, _calls, _buffer = make_context(unknown_runtime)
    unknown: Result = invoke(["remove", "volume", "shared", "--yes"], unknown_context)

    # Require the unavailable-reference refusal without guessing.
    assert unknown.exit_code == 1
    assert "  ?\n" in unknown.stdout
    assert unknown.stderr == "Error: Volume `shared` reference information is unavailable.\n"
    assert unknown_runtime.remove_volume_requests == []
    assert unknown_runtime.inspect_volume("shared") is not None


# Verify a declined confirmation aborts and a surviving volume reports the postcondition.
def test_remove_volume_confirmation_and_incomplete_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    # Decline the confirmation prompt.
    declined_runtime = FakeRuntime()
    declined_runtime.add_volume("shared")
    declined_context, _calls, _buffer = make_context(declined_runtime)
    declined: Result = invoke(["remove", "volume", "shared"], declined_context, input = "n\n")

    # Require an abort without a removal call.
    assert declined.exit_code == 1
    assert "Aborted!" in declined.output
    assert declined_runtime.remove_volume_requests == []
    assert declined_runtime.inspect_volume("shared") is not None

    # Accept the confirmation prompt without `--yes`.
    accepted_runtime = FakeRuntime()
    accepted_runtime.add_volume("shared")
    accepted_context, _calls, _buffer = make_context(accepted_runtime)
    accepted: Result = invoke(["remove", "volume", "shared"], accepted_context, input = "y\n")

    # Require the prompt text and the removal.
    assert accepted.exit_code == 0, accepted.stderr
    assert "Are you sure you want to remove this volume?" in accepted.stdout
    assert accepted_runtime.remove_volume_requests == ["shared"]

    # Report a volume that survives its removal.
    surviving_runtime = FakeRuntime()
    surviving_runtime.add_volume("shared")

    def fail_removal(name: str) -> None:
        # Raise the volume postcondition failure.
        raise IncompleteRemoval("volume", name, backend = "docker")

    # Substitute the failing removal call.
    monkeypatch.setattr(surviving_runtime, "remove_volume", fail_removal)
    surviving_context, _calls, _buffer = make_context(surviving_runtime)
    surviving: Result = invoke(["remove", "volume", "shared", "--yes"], surviving_context)

    # Require the plain postcondition failure on stderr with the command failure class.
    assert surviving.exit_code == 1
    assert surviving.stdout.startswith("\nVolume\n")
    assert surviving.stderr == "Error: Incomplete removal of `docker` volume `shared`.\n"
    assert surviving_runtime.inspect_volume("shared") is not None


# Verify invalid names are Click usage errors on both commands and construct no client.
def test_volume_name_validation_exits_two_before_the_client() -> None:
    # Fail the test if any invalid name constructs a client.
    def fail(_home: Path) -> SandboxClient:
        # Throw a programming failure when validation was bypassed.
        raise AssertionError("invalid volume names must not construct a client.")

    # Reject invalid names on both commands.
    for args in (
        ["create", "volume", "a"],
        ["create", "volume", "has space"],
        ["remove", "volume", "a", "--yes"],
        ["remove", "volume", ".leading", "--yes"],
    ):
        # Invoke the complete command tree with a failing factory.
        result: Result = CliRunner().invoke(cli, args, obj = CliContext(client_factory = FunctionClientFactory(fail)), prog_name = "sandbox")

        # Require the Click usage class and message.
        assert result.exit_code == 2, result.stderr
        assert "Invalid value for 'NAME'" in result.stderr


# Verify progress is transient stderr on a TTY and absent under a pipe.
def test_volume_progress_is_tty_only() -> None:
    # Create a volume on a TTY and inspect the transient stream.
    create_runtime = FakeRuntime()
    create_context, _calls, create_buffer = make_context(create_runtime, tty = True)
    created: Result = invoke(["create", "volume", "fresh"], create_context)

    # Require the SDK phase on stderr and the success result on stdout.
    assert created.exit_code == 0, created.stderr
    assert "Ensuring volume `fresh`" in strip_ansi(create_buffer.getvalue())
    assert "Ensuring volume" not in created.stdout
    assert "Provisioning a `docker` volume" not in created.stdout

    # Remove a volume on a TTY and inspect the transient stream.
    remove_runtime = FakeRuntime()
    remove_runtime.add_volume("shared")
    remove_context, _calls, remove_buffer = make_context(remove_runtime, tty = True)
    removed: Result = invoke(["remove", "volume", "shared", "--yes"], remove_context)

    # Require the removal phase on stderr and no persistent progress prose.
    assert removed.exit_code == 0, removed.stderr
    assert "Removing volume `shared`" in strip_ansi(remove_buffer.getvalue())
    assert "Removing volume" not in removed.stdout
    assert "Removing `docker` volume" not in removed.stdout

    # Require no transient bytes under a pipe.
    pipe_runtime = FakeRuntime()
    pipe_context, _calls, pipe_buffer = make_context(pipe_runtime)
    piped: Result = invoke(["create", "volume", "piped"], pipe_context)
    assert piped.exit_code == 0
    assert pipe_buffer.getvalue() == ""


# Verify help documents the preserved arguments and options without a client.
def test_volume_help_constructs_no_client() -> None:
    # Fail the test if help constructs a client.
    def fail(_home: Path) -> SandboxClient:
        # Throw a programming failure when help probed the SDK.
        raise AssertionError("help must not construct a client.")

    # Build the inert context once.
    context: CliContext = CliContext(client_factory = FunctionClientFactory(fail))

    # Require the preserved create argument help.
    created: Result = invoke(["create", "volume", "--help"], context)
    assert created.exit_code == 0, created.stderr
    assert "NAME" in created.stdout
    assert "The name of the volume to create." in created.stdout
    assert "--name" not in created.stdout
    assert created.stderr == ""

    # Require the preserved remove argument and confirmation option help.
    removed: Result = invoke(["remove", "volume", "--help"], context)
    assert removed.exit_code == 0, removed.stderr
    assert "The name of the managed `docker` volume to remove." in removed.stdout
    assert "-y, --yes" in removed.stdout
    assert "Skip the removal confirmation prompt." in removed.stdout
    assert removed.stderr == ""


# Allow the focused tests to run directly.
if __name__ == "__main__":
    # Run pytest for this file.
    raise SystemExit(pytest.main([__file__]))
