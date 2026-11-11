"""Verify the SDK-backed CLI foundation, read commands, and lifecycle commands."""

# Imports.
from __future__ import annotations

from sdk_fixtures import FunctionClientFactory

import io
from pathlib import Path

import click
import pytest
from click.testing import CliRunner, Result
from rich.console import Console

# Import the CLI group and context.
from sandbox.cli.context import CliContext, default_home
from sandbox.cli.group import SandboxGroup, cli, main
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter, prerequisite_message
from sandbox.cli.presentation.output import CliOutput
from sandbox.cli.presentation.table import TableRenderer
from sandbox.cli.presentation.text import strip_ansi
from sandbox.cli.presentation.vocabulary import NEUTRAL_VOCABULARY, RuntimeVocabulary

# Import domain observations.
from sandbox.domain import BoxObservation, BoxState, Mount, Network, Provenance, RuntimeRef, Workspace

# Import public errors and command facts.
from sandbox.errors import SandboxError
from sandbox.errors.base import CommandFailure
from sandbox.errors.boxes import BoxNotFound
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind
from sandbox.errors.volumes import VolumeCreateFailed, VolumeInUse

# Import the SDK client and temporary fake ports.
from sandbox.sdk import SandboxClient
from sandbox.ports.output import SILENT
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime

# Define the Docker-compatible vocabulary used by composition in production.
DOCKER_VOCABULARY: RuntimeVocabulary = RuntimeVocabulary(
    backend = "docker",
    title = "Container",
    tool = "`docker`",
    noun = "container",
    plural = "containers",
)


# Build one observed box with optional fields.
def observation(
    name: str = "demo",
    state: BoxState = BoxState.RUNNING,
    *,
    status_text: str | None = None,
    workspace: Workspace | None = None,
    mounts: tuple[Mount, ...] | None = None,
    networks: tuple[Network, ...] | None = None,
) -> BoxObservation:
    # Return the fixed observation.
    return BoxObservation(
        name = name,
        state = state,
        provenance = Provenance(catalogue = "default", recipe = "base"),
        status_text = state.value if status_text is None else status_text,
        image = "development-base:ubuntu26.04",
        working_directory = f"/projects/{name}",
        workspace = workspace,
        mounts = mounts,
        networks = networks,
        backend = RuntimeRef(id = f"cid-{name}-0123456789", name = f"{name}-workspace-1"),
    )


# Build a pipe-safe console and presentation for command tests.
def make_presentation(*, tty: bool = False, vocabulary: RuntimeVocabulary = DOCKER_VOCABULARY) -> tuple[CliPresentation, io.StringIO]:
    # Capture the stderr console separately from Click streams.
    buffer = io.StringIO()

    # Construct a console with deterministic width and no markup.
    console = Console(
        file = buffer,
        force_terminal = tty,
        force_interactive = tty,
        color_system = None if not tty else "standard",
        width = 80,
        markup = False,
        emoji = False,
        highlight = False,
    )

    # Return the presentation and its captured stream.
    return CliPresentation(err = console, is_terminal = tty, vocabulary = vocabulary), buffer


# Build one injected CLI context over a real SDK client and fake ports.
def make_context(
    runtime: FakeRuntime | None = None,
    builder: FakeBuilder | None = None,
    *,
    tty: bool = False,
    vocabulary: RuntimeVocabulary = DOCKER_VOCABULARY,
) -> tuple[CliContext, FakeRuntime, list[Path], io.StringIO]:
    # Resolve the fake ports.
    selected_runtime: FakeRuntime = runtime or FakeRuntime()
    selected_builder: FakeBuilder = builder or FakeBuilder()
    presentation: CliPresentation
    buffer: io.StringIO
    presentation, buffer = make_presentation(tty = tty, vocabulary = vocabulary)

    # Record requested homes.
    homes: list[Path] = []

    # Build one client per requested home with the presentation sink.
    def factory(home: Path) -> SandboxClient:
        # Record the home binding.
        homes.append(home)

        # Construct the public client.
        return SandboxClient(home = home, runtime = selected_runtime, builder = selected_builder, output = presentation.output)

    # Build the CLI context.
    context: CliContext = CliContext(
        presentation = presentation,
        errors = ErrorPresenter(vocabulary),
        client_factory = FunctionClientFactory(factory),
    )

    # Return the context and test facts.
    return context, selected_runtime, homes, buffer


# Invoke the root group with the injected context.
def invoke(args: list[str], context: CliContext, *, env: dict[str, str] | None = None) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = context, env = env, prog_name = "sandbox")


# Verify help, version, and completion are Click-owned and construct no client.
def test_help_version_and_completion_construct_no_client() -> None:
    # Fail the test if any command constructs a client.
    def factory(_home: Path) -> SandboxClient:
        # Report an eager probe.
        raise AssertionError("help/version/completion must not construct a client")

    # Build a context with the failing factory.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Verify root help.
    help_result: Result = invoke(["--help"], context)
    assert help_result.exit_code == 0
    assert "Commands:" in help_result.stdout
    assert "status" in help_result.stdout

    # Verify command help keeps the Arguments heading.
    status_help: Result = invoke(["status", "--help"], context)
    assert status_help.exit_code == 0
    assert "Arguments:" in status_help.stdout
    assert "Options:" in status_help.stdout
    assert "--path" in status_help.stdout

    # Verify version.
    version_result: Result = invoke(["--version"], context)
    assert version_result.exit_code == 0
    assert version_result.stdout.strip()

    # Verify every supported completion script without a client.
    for shell in ("bash", "zsh", "powershell"):
        script: Result = invoke(["completions", shell], context)
        assert script.exit_code == 0, script.stderr
        assert script.stdout
        assert "fish" not in script.stdout.lower()
        assert "\x1b" not in script.stdout

    # Verify Fish remains a Click usage error.
    fish: Result = invoke(["completions", "fish"], context)
    assert fish.exit_code == 2
    assert "Invalid value" in fish.stderr


# Verify pipe output ignores FORCE_COLOR, TTY_COMPATIBLE, COLUMNS, and help markup.
def test_help_is_plain_and_pipe_pinned() -> None:
    # Build a context whose client is never needed.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY))

    # Request help with hostile color and width environment variables.
    result: Result = invoke(
        ["status", "--help"],
        context,
        env = {
            "FORCE_COLOR": "1",
            "TTY_COMPATIBLE": "1",
            "COLUMNS": "500",
            "TERM": "xterm-256color",
        },
    )

    # Require plain deterministic help.
    assert result.exit_code == 0
    assert "\x1b" not in result.stdout
    assert "Arguments:" in result.stdout
    assert max(len(line) for line in result.stdout.splitlines()) <= 80


# Verify output progress and child rendering are TTY-only and pipe-safe.
def test_tty_progress_and_pipe_suppression() -> None:
    # Seed one stopped box so start changes state.
    runtime = FakeRuntime()
    runtime.add_box(observation(state = BoxState.STOPPED))

    # Run a TTY invocation and inspect its transient stream.
    tty_context, _runtime, _homes, tty_buffer = make_context(runtime, tty = True)
    tty_result: Result = invoke(["start", "demo"], tty_context)
    assert tty_result.exit_code == 0, tty_result.stderr
    tty_text: str = strip_ansi(tty_buffer.getvalue())
    assert "Starting box `demo`" in tty_text

    # Run a pipe invocation and require no transient stream.
    pipe_context, _runtime, _homes, pipe_buffer = make_context(runtime, tty = False)
    pipe_result: Result = invoke(["start", "demo"], pipe_context)
    assert pipe_result.exit_code == 0
    assert pipe_buffer.getvalue() == ""


# Verify opaque child output keeps its channel mapping and strips pipe controls.
def test_child_output_is_plain_on_a_pipe_and_raw_on_a_terminal() -> None:
    # Render split UTF-8 and ANSI under a pipe.
    pipe_buffer = io.StringIO()
    pipe_console = Console(file = pipe_buffer, force_terminal = False, color_system = None, width = 80, markup = False, emoji = False, highlight = False)
    pipe_sink = CliOutput(pipe_console, is_terminal = False)
    pipe_sink.process_output("stdout", b"caf\xc3")  # pyright: ignore[reportArgumentType]
    pipe_sink.process_output("stdout", b"\xa9 \x1b[31mred\x1b[0m\x07\n")  # pyright: ignore[reportArgumentType]
    pipe_sink.close()
    assert pipe_buffer.getvalue() == "café red\n"

    # Render the same child ANSI on a terminal.
    tty_buffer = io.StringIO()
    tty_console = Console(
        file = tty_buffer,
        force_terminal = True,
        force_interactive = True,
        color_system = "standard",
        width = 80,
        markup = False,
        emoji = False,
        highlight = False,
    )
    tty_sink = CliOutput(tty_console, is_terminal = True)
    tty_sink.process_output("stdout", b"\x1b[31mred\x1b[0m\n")  # pyright: ignore[reportArgumentType]
    tty_sink.close()
    assert "\x1b[31mred\x1b[0m" in tty_buffer.getvalue()


# Verify attachment policy pins width and color for a pipe.
def test_attach_pins_pipe_console_policy() -> None:
    # Build the production presentation in this non-TTY test process.
    presentation: CliPresentation = CliPresentation.attach()

    # Require the deterministic pipe console.
    assert presentation.is_terminal is False
    assert presentation.err.width == 80
    assert presentation.err.color_system is None

    # Finalize the presentation.
    presentation.close()


# Verify tables keep headers, order, alignment, and incidental padding.
def test_table_renderer_preserves_compatibility_bytes() -> None:
    # Capture one rendered table.
    @click.command()
    def command() -> None:
        # Render two left-aligned rows.
        TableRenderer().render(("NAME", "STATUS"), [("short", "running"), ("a-longer-name", "up")])

    # Invoke the command.
    result: Result = CliRunner().invoke(command, [])

    # Require exactly the compatibility bytes.
    assert result.exit_code == 0
    assert result.stdout == (
        "NAME           STATUS \n"
        "short          running\n"
        "a-longer-name  up     \n"
    )


# Verify table values strip ANSI and control characters before width calculation.
def test_table_strips_untrusted_display_sequences() -> None:
    # Render an injected name and target.
    @click.command()
    def command() -> None:
        # Render one hostile row.
        TableRenderer().render(("NAME", "TARGET"), [("\x1b[31mbad\x1b[0m\x07", "a\x1b[2Jb")])

    # Invoke the command.
    result: Result = CliRunner().invoke(command, [])

    # Require plain text without terminal controls.
    assert result.exit_code == 0
    assert "\x1b" not in result.stdout
    assert "\x07" not in result.stdout
    assert "bad" in result.stdout
    assert "ab" in result.stdout


# Verify status renders the compatibility report and mount categories.
def test_status_renders_the_full_report() -> None:
    # Seed one running observation with every mount category.
    runtime = FakeRuntime()
    runtime.add_box(
        observation(
            mounts = (
                Mount(kind = "bind", source = "/host/secret", target = "/run/secrets/zeta-secret"),
                Mount(kind = "volume", source = "example-state", target = "/home/example/.state"),
                Mount(kind = "bind", source = "/host/project", target = "/projects/demo"),
                Mount(kind = "bind", source = "/host/other", target = "/run/secrets/alpha-secret"),
            ),
            networks = (
                Network(name = "default", ip_address = "172.18.0.2"),
                Network(name = "tooling", ip_address = ""),
            ),
        ),
    )
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Render the report.
    result: Result = invoke(["status", "demo"], context)

    # Require the identity and configuration labels.
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    assert "Project          demo" in result.stdout
    assert "Container ID      cid-demo-012" in result.stdout
    assert "Container name    demo-workspace-1" in result.stdout
    assert "Status            running" in result.stdout
    assert "Image             development-base:ubuntu26.04" in result.stdout
    assert "Working directory /projects/demo" in result.stdout

    # Require the mount, secret, and network sections.
    assert "Volumes" in result.stdout
    assert "  example-state -> /home/example/.state" in result.stdout
    assert "Bind mounts" in result.stdout
    assert "  /host/project -> /projects/demo" in result.stdout
    assert "Secrets" in result.stdout
    assert "  alpha-secret -> /run/secrets/alpha-secret" in result.stdout
    assert "  zeta-secret -> /run/secrets/zeta-secret" in result.stdout
    assert result.stdout.index("alpha-secret") < result.stdout.index("zeta-secret")
    assert "Networks" in result.stdout
    assert "  default -> 172.18.0.2" in result.stdout
    assert "  tooling" in result.stdout


# Verify status distinguishes reported-empty from unavailable observations.
def test_status_empty_and_unavailable_markers() -> None:
    # Report explicitly empty mounts and networks.
    empty_runtime = FakeRuntime()
    empty_runtime.add_box(observation(mounts = (), networks = ()))
    empty_context, _runtime, _homes, _buffer = make_context(empty_runtime)
    empty_result: Result = invoke(["status", "demo"], empty_context)
    assert empty_result.exit_code == 0
    assert empty_result.stdout.count("  None") == 4

    # Report unavailable mounts and networks.
    unknown_runtime = FakeRuntime()
    unknown_runtime.add_box(observation(mounts = None, networks = None))
    unknown_context, _runtime, _homes, _buffer = make_context(unknown_runtime)
    unknown_result: Result = invoke(["status", "demo"], unknown_context)
    assert unknown_result.exit_code == 0
    assert unknown_result.stdout.count("  ?") == 4


# Verify status --path prints only the raw host directory.
def test_status_path_is_raw_stdout(tmp_path: Path) -> None:
    # Create the reported workspace directory.
    project_dir: Path = tmp_path / "project"
    project_dir.mkdir()
    runtime = FakeRuntime()
    runtime.add_box(observation(workspace = Workspace(host_directory = project_dir.resolve(), target = "/projects/demo")))
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Render the path.
    result: Result = invoke(["status", "demo", "--path"], context)

    # Require exactly the path plus newline and no stderr.
    assert result.exit_code == 0
    assert result.stdout == f"{project_dir.resolve()}\n"
    assert result.stderr == ""


# Verify status --path keeps its CLI-local failures on stderr.
def test_status_path_rejects_missing_bind_and_directory(tmp_path: Path) -> None:
    # Reject a missing project bind.
    missing_bind_runtime = FakeRuntime()
    missing_bind_runtime.add_box(observation(workspace = None))
    bind_context, _runtime, _homes, _buffer = make_context(missing_bind_runtime)
    bind_result: Result = invoke(["status", "demo", "--path"], bind_context)
    assert bind_result.exit_code == 1
    assert bind_result.stdout == ""
    assert "Error: Box `demo` has no project directory bind mount." in bind_result.stderr

    # Reject a project directory that no longer exists.
    removed: Path = (tmp_path / "removed").resolve()
    missing_dir_runtime = FakeRuntime()
    missing_dir_runtime.add_box(observation(workspace = Workspace(host_directory = removed, target = "/projects/demo")))
    dir_context, _runtime, _homes, _buffer = make_context(missing_dir_runtime)
    dir_result: Result = invoke(["status", "demo", "--path"], dir_context)
    assert dir_result.exit_code == 1
    assert dir_result.stdout == ""
    assert f"Project directory `{removed}` for box `demo` no longer exists." in dir_result.stderr


# Verify an absent box uses the injected runtime vocabulary.
def test_status_absent_box_uses_runtime_vocabulary() -> None:
    # Query a missing box with Docker vocabulary.
    context, _runtime, _homes, _buffer = make_context()
    result: Result = invoke(["status", "missing"], context)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: No `docker` container exists for project `missing`.\n"

    # Query with an explicitly neutral vocabulary.
    neutral = RuntimeVocabulary(
        backend = "sandbox",
        title = "Sandbox",
        tool = "`sandbox`",
        noun = "box",
        plural = "boxes",
    )
    neutral_context, _runtime, _homes, _buffer = make_context(vocabulary = neutral)
    neutral_result: Result = invoke(["status", "missing"], neutral_context)
    assert neutral_result.exit_code == 1
    assert neutral_result.stderr == "Error: No `sandbox` box exists for project `missing`.\n"


# Verify list boxes renders the compatibility table in name order.
def test_list_boxes_table_and_empty_state() -> None:
    # Seed two boxes out of alphabetical order.
    runtime = FakeRuntime()
    runtime.add_box(observation("zeta"))
    runtime.add_box(observation("alpha"))
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Render the boxes.
    result: Result = invoke(["list", "boxes"], context)
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    lines: list[str] = result.stdout.rstrip("\n").splitlines()
    assert lines[0].split() == ["PROJECT", "STATUS", "IMAGE", "WORKING", "DIRECTORY"]
    assert lines[1].startswith("alpha")
    assert lines[2].startswith("zeta")
    assert "running" in lines[1]
    assert "development-base:ubuntu26.04" in lines[1]

    # Render the empty state.
    empty_context, _runtime, _homes, _buffer = make_context(FakeRuntime())
    empty_result: Result = invoke(["list", "boxes"], empty_context)
    assert empty_result.exit_code == 0
    assert empty_result.stdout == "No `sandbox`-managed boxes found.\n"


# Verify list volumes renders the compatibility table and empty state.
def test_list_volumes_table_and_empty_state() -> None:
    # Seed two managed volumes out of name order.
    runtime = FakeRuntime()
    runtime.ensure_volume("zeta")
    runtime.ensure_volume("shared")
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Render the volumes.
    result: Result = invoke(["list", "volumes"], context)
    assert result.exit_code == 0, result.stderr
    lines: list[str] = result.stdout.rstrip("\n").splitlines()
    assert lines[0].split() == ["NAME", "DRIVER", "CONTAINERS"]
    assert lines[1].split() == ["shared", "local", "0"]
    assert lines[2].split() == ["zeta", "local", "0"]

    # Render the empty state.
    empty_context, _runtime, _homes, _buffer = make_context(FakeRuntime())
    empty_result: Result = invoke(["list", "volumes"], empty_context)
    assert empty_result.exit_code == 0
    assert empty_result.stdout == "No `sandbox`-managed `docker` volumes found.\n"


# Verify list output stays plain under a hostile color environment.
def test_list_is_plain_under_a_pipe() -> None:
    # Seed one box.
    runtime = FakeRuntime()
    runtime.add_box(observation())
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Render with forced color and width.
    result: Result = invoke(
        ["list", "boxes"],
        context,
        env = {"FORCE_COLOR": "1", "TTY_COMPATIBLE": "1", "COLUMNS": "500", "TERM": "xterm-256color"},
    )

    # Require plain text and no wrapping of long content.
    assert result.exit_code == 0
    assert "\x1b" not in result.stdout
    assert "development-base:ubuntu26.04" in result.stdout
    assert "/projects/demo" in result.stdout


# Verify start and stop preserve success, skip, and runtime request behavior.
def test_start_and_stop_report_both_outcomes() -> None:
    # Start a stopped box.
    start_runtime = FakeRuntime()
    start_runtime.add_box(observation(state = BoxState.STOPPED))
    start_context, _runtime, _homes, _buffer = make_context(start_runtime)
    start_result: Result = invoke(["start", "demo"], start_context)
    assert start_result.exit_code == 0
    assert start_result.stdout == "Successfully started the box for project `demo`.\n"
    assert start_runtime.start_requests == ["demo"]

    # Skip an already running box.
    skip_start_context, _runtime, _homes, _buffer = make_context(start_runtime)
    skip_start: Result = invoke(["start", "demo"], skip_start_context)
    assert skip_start.exit_code == 0
    assert skip_start.stdout == "Skipped starting the box for project `demo` because it is already running.\n"

    # Stop a running box.
    stop_runtime = FakeRuntime()
    stop_runtime.add_box(observation())
    stop_context, _runtime, _homes, _buffer = make_context(stop_runtime)
    stop_result: Result = invoke(["stop", "demo"], stop_context)
    assert stop_result.exit_code == 0
    assert stop_result.stdout == "Successfully stopped the box for project `demo`.\n"
    assert stop_runtime.stop_requests == ["demo"]

    # Skip an already stopped box.
    skip_stop_context, _runtime, _homes, _buffer = make_context(stop_runtime)
    skip_stop: Result = invoke(["stop", "demo"], skip_stop_context)
    assert skip_stop.exit_code == 0
    assert skip_stop.stdout == "Skipped stopping the box for project `demo` because it is already stopped.\n"


# Verify a missing lifecycle box is presented once on stderr.
def test_start_missing_box_is_a_stderr_error() -> None:
    # Start an unknown project.
    context, _runtime, _homes, _buffer = make_context()
    result: Result = invoke(["start", "missing"], context)

    # Require the current message and exit class.
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: No `docker` container exists for project `missing`.\n"


# Verify enter forwards options and preserves shell status classes.
def test_enter_forwards_and_preserves_shell_status() -> None:
    # Seed one running box with a zero shell status.
    runtime = FakeRuntime()
    runtime.add_box(observation())
    context, _runtime, _homes, _buffer = make_context(runtime)
    success: Result = invoke(["enter", "demo", "--shell", "bash", "--no-login"], context)
    assert success.exit_code == 0
    assert success.stdout == ""
    assert success.stderr == ""
    assert runtime.enter_requests[0].name == "demo"
    assert runtime.enter_requests[0].shell == "bash"
    assert runtime.enter_requests[0].login is False

    # Preserve a positive shell status.
    positive_runtime = FakeRuntime(enter_status = 7)
    positive_runtime.add_box(observation())
    positive_context, _runtime, _homes, _buffer = make_context(positive_runtime)
    positive: Result = invoke(["enter", "demo"], positive_context)
    assert positive.exit_code == 7
    assert positive.stdout == ""
    assert "Error:" not in positive.stderr

    # Normalize a signal-like status to one.
    signal_runtime = FakeRuntime(enter_status = -9)
    signal_runtime.add_box(observation())
    signal_context, _runtime, _homes, _buffer = make_context(signal_runtime)
    signal: Result = invoke(["enter", "demo"], signal_context)
    assert signal.exit_code == 1
    assert "Error:" not in signal.stderr


# Verify prerequisite messages route Compose and git facts to their templates.
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            PrerequisiteError("docker compose", PrerequisiteKind.MISSING),
            "Docker Compose is required but `docker compose` is not available. Install the Compose plugin (>= 5.6.0).",
        ),
        (
            PrerequisiteError("docker compose", PrerequisiteKind.VERSION, requirement = ">=5.6.0", found = "5.5.9"),
            "Docker Compose 5.5.9 is too old; version 5.6.0 or newer is required.",
        ),
        (
            PrerequisiteError("docker compose", PrerequisiteKind.UNUSABLE, diagnostic = "permission denied"),
            "Docker Compose is installed but unusable: permission denied.",
        ),
        (
            PrerequisiteError("git", PrerequisiteKind.MISSING),
            "`git` is required to install `git` catalogue sources but was not found. Install git and ensure it is on PATH.",
        ),
        (
            PrerequisiteError("git", PrerequisiteKind.UNUSABLE, diagnostic = "denied", hint = "Ensure the `git` executable can run and retry."),
            "Ensure the `git` executable can run and retry.",
        ),
    ],
)
def test_prerequisite_messages_use_the_tool_and_structured_facts(error: PrerequisiteError, message: str) -> None:
    # Render the prerequisite through the single presenter template set.
    assert prerequisite_message(error) == message


# Verify the presenter preserves a positive engine status and streams.
def test_error_presenter_preserves_engine_status() -> None:
    # Queue one engine failure with a positive status.
    runtime = FakeRuntime()
    runtime.add_box(observation())
    runtime.fail_next(
        EngineFailure(
            CommandFailure(
                backend = "docker",
                operation = "start",
                command = ("docker", "start", "cid"),
                exit_code = 125,
                diagnostic = "conflict",
                timed_out = False,
            ),
        ),
    )
    context, _runtime, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["start", "demo"], context)

    # Require the compatibility command template and status.
    assert result.exit_code == 125
    assert result.stdout == ""
    assert result.stderr == "Error: `docker start cid` failed with exit code 125: conflict.\n"


# Verify generic public failures are presented plain and exit 1.
def test_error_presenter_handles_the_error_root() -> None:
    # Fail the factory with a public root failure.
    def factory(_home: Path) -> SandboxClient:
        # Raise the public root directly.
        raise SandboxError("neutral failure")

    # Build the failing context.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))
    result: Result = invoke(["start", "demo"], context)

    # Require the single plain presenter.
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: neutral failure\n"


# Verify Click usage keeps exit 2 and abort stays Click-owned.
def test_click_usage_and_abort_are_unchanged() -> None:
    # Reject an invalid project identifier before any client work.
    context, _runtime, _homes, _buffer = make_context()
    usage: Result = invoke(["status", "Bad"], context)
    assert usage.exit_code == 2
    assert usage.stdout == ""
    assert "Usage:" in usage.stderr
    assert "Invalid value for 'PROJECT'" in usage.stderr

    # Let Click abort with its preserved stream behavior.
    def aborting_factory(_home: Path) -> SandboxClient:
        # Trigger a confirmation-style abort.
        raise click.Abort()

    presentation, _buffer = make_presentation()
    abort_context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(aborting_factory))
    aborted: Result = invoke(["stop", "demo"], abort_context)
    assert aborted.exit_code == 1
    assert "Aborted!" in aborted.stderr
    assert "Error:" not in aborted.stderr


# Verify an interruption is not translated into the public presenter.
def test_keyboard_interrupt_is_not_translated() -> None:
    # Interrupt the client construction path.
    def interrupting_factory(_home: Path) -> SandboxClient:
        # Raise the process-level interruption.
        raise KeyboardInterrupt()

    # Build the interrupting context.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(interrupting_factory))
    result: Result = invoke(["start", "demo"], context)

    # Require Click's abort path without an `Error:` presenter line.
    assert result.exit_code == 1
    assert "Error:" not in result.stderr


# Verify commands bind the default home through the injected factory.
def test_commands_bind_the_default_home() -> None:
    # Build a context and run a read command.
    context, _runtime, homes, _buffer = make_context(FakeRuntime())
    result: Result = invoke(["list", "boxes"], context)

    # Require one default-home binding.
    assert result.exit_code == 0
    assert homes == [default_home()]


# Verify the context helper resolves a client and enforces configuration.
def test_client_for_requires_a_factory() -> None:
    # Build a context without a client factory.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY))

    # Invoke a command that needs one.
    result: Result = invoke(["list", "boxes"], context)
    assert result.exit_code == 1
    assert result.stderr == "Error: No `sandbox` client factory is configured.\n"


# Verify the styled group preserves the abort exception path.
def test_sandbox_group_is_the_root_group_type() -> None:
    # Require the presenter hook on the registered root.
    assert isinstance(cli, SandboxGroup)


# Allow the focused tests to run directly.
if __name__ == "__main__":
    # Run pytest for this file.
    raise SystemExit(pytest.main([__file__]))


# Record the injected home and sink for a protocol-shaped client factory.
class ProtocolFactory:
    # Retain the shared fake ports and recorded calls.
    def __init__(self, runtime: FakeRuntime, builder: FakeBuilder | None = None) -> None:
        self.runtime = runtime
        self.builder = builder or FakeBuilder()
        self.calls: list[tuple[Path, object]] = []

    # Build one client for the requested home and presentation sink.
    def for_home(self, home: Path, *, output = SILENT) -> SandboxClient:
        # Record the exact factory inputs.
        self.calls.append((home, output))

        # Build the SDK client over the recorded fake ports.
        return SandboxClient(home = home, runtime = self.runtime, builder = self.builder, output = output)


# Verify the protocol factory receives the default home and presentation sink.
def test_protocol_factory_receives_home_and_output_sink() -> None:
    # Seed one observed box and a protocol-shaped factory.
    runtime = FakeRuntime()
    runtime.add_box(observation())
    factory = ProtocolFactory(runtime)
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, client_factory = FunctionClientFactory(factory), vocabulary = DOCKER_VOCABULARY)

    # Run a read command through the injected factory.
    result: Result = invoke(["list", "boxes"], context)

    # Require one binding to the default home and the presentation sink.
    assert result.exit_code == 0, result.stderr
    assert factory.calls == [(default_home(), presentation.output)]
    assert context.client_factory is factory or getattr(context.client_factory, "_factory", None) is factory


# Verify TTY progress flows through the factory-injected SDK client.
def test_tty_progress_flows_through_the_protocol_factory() -> None:
    # Seed a stopped box so start emits progress.
    runtime = FakeRuntime()
    runtime.add_box(observation(state = BoxState.STOPPED))
    factory = ProtocolFactory(runtime)
    presentation, buffer = make_presentation(tty = True)
    context = CliContext(presentation = presentation, client_factory = FunctionClientFactory(factory), vocabulary = DOCKER_VOCABULARY)

    # Start the box and inspect the transient stderr status.
    result: Result = invoke(["start", "demo"], context)

    assert result.exit_code == 0, result.stderr
    assert "Starting box `demo`" in strip_ansi(buffer.getvalue())


# Verify Docker vocabulary is the direct-Click fallback.
def test_docker_vocabulary_is_the_default_fallback() -> None:
    # Build a context without an injected vocabulary or console.
    context = CliContext.create()

    assert context.vocabulary.backend == "docker"
    assert context.vocabulary.label == "Container"
    assert NEUTRAL_VOCABULARY is not None


# Verify the integration-owned group shells are registered.
def test_create_list_and_remove_group_shells_are_registered() -> None:
    # Request root help.
    context, _runtime, _homes, _buffer = make_context()
    result: Result = invoke(["--help"], context)

    assert result.exit_code == 0
    assert "create" in result.stdout
    assert "list" in result.stdout
    assert "remove" in result.stdout


# Verify project completion filters running and exited boxes without eager clients.
def test_project_completion_filters_states_through_the_factory() -> None:
    # Seed running, stopped, and created boxes.
    runtime = FakeRuntime()
    runtime.add_box(observation("demo", BoxState.RUNNING))
    runtime.add_box(observation("stopped", BoxState.STOPPED, status_text = "exited"))
    runtime.add_box(observation("fresh", BoxState.CREATED))
    factory = ProtocolFactory(runtime)
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, client_factory = FunctionClientFactory(factory), vocabulary = DOCKER_VOCABULARY)

    # Request start completion, which offers exited boxes only.
    result: Result = invoke(
        [],
        context,
        env = {"_SANDBOX_COMPLETE": "bash_complete", "COMP_WORDS": "sandbox start ", "COMP_CWORD": "2"},
    )

    assert result.exit_code == 0, result.output
    assert "plain,stopped" in result.stdout
    assert "plain,demo" not in result.stdout
    assert "plain,fresh" not in result.stdout
    assert len(factory.calls) == 1


# Verify every project command completes the documented box states.
def test_project_completion_filters_every_command() -> None:
    # Seed running, stopped, and created boxes.
    runtime = FakeRuntime()
    runtime.add_box(observation("demo", BoxState.RUNNING))
    runtime.add_box(observation("stopped", BoxState.STOPPED, status_text = "exited"))
    runtime.add_box(observation("fresh", BoxState.CREATED))
    context, _runtime, _homes, _buffer = make_context(runtime)

    # Declare each command line and its expected projects.
    cases: tuple[tuple[str, set[str]], ...] = (
        ("sandbox enter ", {"demo"}),
        ("sandbox stop ", {"demo"}),
        ("sandbox start ", {"stopped"}),
        ("sandbox status ", {"demo", "stopped", "fresh"}),
        ("sandbox remove box ", {"demo", "stopped", "fresh"}),
    )

    # Check every command's completion filter.
    for words, expected in cases:
        result: Result = invoke(
            [],
            context,
            env = {"_SANDBOX_COMPLETE": "bash_complete", "COMP_WORDS": words, "COMP_CWORD": str(len(words.split()) - (0 if words.endswith(" ") else 1))},
        )
        assert result.exit_code == 0, result.output
        completed: set[str] = {
            line.split(",", 1)[1]
            for line in result.stdout.splitlines()
            if line.startswith("plain,")
        }
        assert completed == expected, (words, completed)


# Verify completion failures fall back to no suggestions without a client error.
def test_project_completion_tolerates_client_failures() -> None:
    # Use a factory that raises a public failure.
    def fail(_home: Path) -> SandboxClient:
        raise SandboxError("completion unavailable")

    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, client_factory = FunctionClientFactory(fail))
    result: Result = invoke(
        [],
        context,
        env = {"_SANDBOX_COMPLETE": "bash_complete", "COMP_WORDS": "sandbox enter ", "COMP_CWORD": "2"},
    )

    # Require a clean empty completion.
    assert result.exit_code == 0, result.stderr
    assert "plain," not in result.stdout
    assert "Error:" not in result.stderr


# Verify static completion script generation does not construct a client.
def test_completion_script_generation_constructs_no_client() -> None:
    # Use a protocol factory that fails on construction.
    runtime = FakeRuntime()
    factory = ProtocolFactory(runtime)
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, client_factory = FunctionClientFactory(factory), vocabulary = DOCKER_VOCABULARY)

    # Generate every supported script.
    for shell in ("bash", "zsh", "powershell"):
        result: Result = invoke(["completions", shell], context)
        assert result.exit_code == 0, result.stderr
        assert result.stdout
        assert "\x1b" not in result.stdout

    # Require no client construction or host probe.
    assert factory.calls == []


# Verify the presenter maps the documented exit classes and structured errors.
@pytest.mark.parametrize(
    ("error", "exit_code", "message"),
    [
        (SandboxError("plain"), 1, "plain"),
        (BoxNotFound("demo"), 1, "No `docker` container exists for project `demo`."),
        (
            EngineFailure(CommandFailure("docker", "start", ("docker", "start", "cid"), 130, "conflict")),
            130,
            "`docker start cid` failed with exit code 130: conflict.",
        ),
        (
            EngineFailure(CommandFailure("docker", "start", None, 0, "")),
            1,
            "The start operation failed.",
        ),
        (
            VolumeCreateFailed("shared", CommandFailure("docker", "volume.create", ("docker", "volume", "create", "shared"), 17, "denied")),
            17,
            "`docker volume create shared` failed with exit code 17: denied.",
        ),
        (
            VolumeInUse("shared", backend = "docker"),
            1,
            "Volume `shared` is still referenced by `docker` containers.",
        ),
        (
            PrerequisiteError("docker", PrerequisiteKind.MISSING),
            1,
            "required executable `docker` was not found on PATH. Install Docker Engine and ensure it is on PATH.",
        ),
        (
            EngineOutputInvalid("docker", "inspect", "not json"),
            1,
            "Docker returned invalid JSON: 'not json'",
        ),
    ],
)
def test_error_presenter_exit_classes(error: SandboxError, exit_code: int, message: str) -> None:
    # Render through the single presenter into the injected console.
    presentation, buffer = make_presentation()
    presenter = ErrorPresenter(DOCKER_VOCABULARY, console = presentation.err)

    # Require the plain frame, exit class, and message.
    with pytest.raises(SystemExit) as raised:
        presenter.present(error)

    assert raised.value.code == exit_code
    assert buffer.getvalue() == f"Error: {message}\n"
    assert "\x1b" not in buffer.getvalue()


# Verify main presents a public failure escaping the Click invocation.
def test_main_presents_a_failure_escaping_click(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replace Click's entry point with a failing double.
    presentation, buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY, console = presentation.err))

    def fail(*_args: object, **_kwargs: object) -> None:
        raise SandboxError("escaped failure")

    monkeypatch.setattr(cli, "main", fail)

    # Require the single presenter and its exit class.
    with pytest.raises(SystemExit) as raised:
        main(context)

    assert raised.value.code == 1
    assert buffer.getvalue() == "Error: escaped failure\n"
