"""Verify the SDK-backed `remove box` command."""

# Imports.
from __future__ import annotations

from sdk_fixtures import FunctionClientFactory

import io
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rich.console import Console

# Import the CLI group, context, and presentation.
from sandbox.cli.context import CliContext
from sandbox.cli.group import cli
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.text import strip_ansi
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary

# Import domain observations.
from sandbox.domain import BoxObservation, BoxState, Mount, Provenance, RemovalPlan, RuntimeRef

# Import public failure facts.
from sandbox.errors.base import CommandFailure
from sandbox.errors.engine import EngineFailure
from sandbox.errors.ownership import OwnershipViolation
from sandbox.errors.removal import IncompleteRemoval, NetworkInUse

# Import the public SDK and fake ports.
from sandbox.sdk import SandboxClient
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
def make_context(runtime: FakeRuntime, *, tty: bool = False) -> tuple[CliContext, list[Path], io.StringIO]:
    # Capture the presentation and record client bindings.
    presentation, buffer = make_presentation(tty = tty)
    homes: list[Path] = []

    # Build one client per requested home with the presentation sink.
    def factory(home: Path) -> SandboxClient:
        # Record the home.
        homes.append(home)

        # Construct the inert public client over the fake ports.
        return SandboxClient(home = home, runtime = runtime, builder = FakeBuilder(), output = presentation.output)

    # Build the injected CLI context with a Click-owned error presenter.
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Return the context, recorded homes, and transient stream.
    return context, homes, buffer


# Invoke the complete command tree with the injected context.
def invoke(
    args: list[str],
    context: CliContext,
    *,
    input: str | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = context, input = input, env = env, prog_name = "sandbox")


# Build one observed box with the requested removal-relevant facts.
def observation(
    name: str = "demo",
    *,
    state: BoxState = BoxState.RUNNING,
    mounts: tuple[Mount, ...] = (),
) -> BoxObservation:
    # Return the fixed observation.
    return BoxObservation(
        name = name,
        state = state,
        provenance = Provenance(catalogue = "default", recipe = "base"),
        status_text = state.value,
        image = "sandbox/demo:latest",
        working_directory = f"/projects/{name}",
        mounts = mounts,
        backend = RuntimeRef(id = f"cid-{name}", name = f"{name}-workspace-1"),
    )


# Build the removal preview with one container and one network.
def removal_plan(name: str = "demo") -> RemovalPlan:
    # Return the fixed preview.
    return RemovalPlan(
        box = name,
        containers = (RuntimeRef(id = "cid-demo", name = "demo-workspace-1"),),
        networks = (RuntimeRef(id = "nid-demo", name = "demo_default"),),
    )


# Verify the preview is displayed and removal preserves images, volumes, and host directories.
def test_remove_box_displays_the_plan_and_preserves_unmanaged_resources(tmp_path: Path) -> None:
    # Prepare a host project directory, a volume mountpoint, and their markers.
    project_dir: Path = tmp_path / "project"
    project_dir.mkdir()
    project_marker: Path = project_dir / "keep.txt"
    project_marker.write_text("project data\n", encoding = "utf-8")
    volume_dir: Path = tmp_path / "volume-data"
    volume_dir.mkdir()
    volume_marker: Path = volume_dir / "keep.txt"
    volume_marker.write_text("volume data\n", encoding = "utf-8")

    # Seed a box attached to a shared volume and a configured removal preview.
    runtime = FakeRuntime(removal_plan = removal_plan())
    runtime.add_volume("example-state", mountpoint = str(volume_dir))
    runtime.add_box(observation(mounts = (Mount(kind = "volume", source = "example-state", target = "/data"),)))
    context, homes, _buffer = make_context(runtime)

    # Remove the box without prompting.
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the preserved plan display and success message on stdout.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == (
        "\nRemoving resources for project `demo`...\n"
        "\nContainers\n"
        "  demo-workspace-1\n"
        "\nNetworks\n"
        "  demo_default\n"
        "\nPreserved\n"
        "  images\n"
        "  volumes\n"
        "  host project directories\n"
        "Successfully removed resources for project `demo`.\n"
    )
    assert result.stderr == ""
    assert "Remove these resources?" not in result.stdout

    # Require the preview and removal to cross the SDK exactly once.
    assert runtime.removal_requests == ["demo"]
    assert runtime.remove_requests == ["demo"]
    assert runtime.inspect("demo") is None
    assert homes == [Path.home() / ".sandbox"]

    # Require the shared volume and both host directories to survive.
    assert runtime.inspect_volume("example-state") is not None
    assert volume_marker.exists()
    assert project_marker.exists()


# Verify an empty plan still displays the preserved-resource sections.
def test_remove_box_displays_empty_sections() -> None:
    # Seed a box with a preview that has no runtime resources.
    runtime = FakeRuntime(removal_plan = RemovalPlan(box = "demo", containers = (), networks = ()))
    runtime.add_box(observation())
    context, _homes, _buffer = make_context(runtime)

    # Remove the box without prompting.
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the compatibility empty markers.
    assert result.exit_code == 0, result.stderr
    assert result.stdout.count("  None\n") == 2
    assert runtime.remove_requests == ["demo"]


# Verify confirmation accepts, declines with the abort class, and defaults to no.
def test_remove_box_confirmation_accepts_and_aborts() -> None:
    # Accept the confirmation prompt without `--yes`.
    accepted_runtime = FakeRuntime(removal_plan = removal_plan())
    accepted_runtime.add_box(observation())
    accepted_context, _homes, _buffer = make_context(accepted_runtime)
    accepted: Result = invoke(["remove", "box", "demo"], accepted_context, input = "y\n")

    # Require the prompt and the removal.
    assert accepted.exit_code == 0, accepted.stderr
    assert "Remove these resources?" in accepted.stdout
    assert accepted_runtime.remove_requests == ["demo"]
    assert accepted_runtime.inspect("demo") is None

    # Decline the confirmation prompt.
    declined_runtime = FakeRuntime(removal_plan = removal_plan())
    declined_runtime.add_box(observation())
    declined_context, _homes, _buffer = make_context(declined_runtime)
    declined: Result = invoke(["remove", "box", "demo"], declined_context, input = "n\n")

    # Require the abort class without a removal call.
    assert declined.exit_code == 1
    assert "Aborted!" in declined.output
    assert declined_runtime.remove_requests == []
    assert declined_runtime.inspect("demo") is not None

    # Accept the default answer, which is no.
    default_runtime = FakeRuntime(removal_plan = removal_plan())
    default_runtime.add_box(observation())
    default_context, _homes, _buffer = make_context(default_runtime)
    default: Result = invoke(["remove", "box", "demo"], default_context, input = "\n")

    # Require the default to abort without a removal call.
    assert default.exit_code == 1
    assert "Aborted!" in default.output
    assert default_runtime.remove_requests == []


# Verify an absent box reports the preserved error and no plan or removal.
def test_remove_box_reports_absence_with_exit_one() -> None:
    # Attempt to remove an absent box.
    runtime = FakeRuntime()
    context, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the preserved absence error and no stdout plan.
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: No `sandbox` resources exist for project `demo`.\n"
    assert runtime.remove_requests == []


# Verify ownership failures surface through the presenter before display or mutation.
def test_remove_box_reports_ownership_before_mutation() -> None:
    # Queue an ownership refusal from the removal preview.
    runtime = FakeRuntime()
    runtime.fail_next(OwnershipViolation("box", "demo"))
    context, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the single presenter and no plan or mutation.
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: Cannot verify `sandbox` ownership of box `demo`.\n"
    assert runtime.remove_requests == []
    assert runtime.inspect("demo") is None


# Verify a network-in-use refusal is presented after the plan and before further mutation.
def test_remove_box_reports_network_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed a box and a plan whose removal refuses the shared network.
    runtime = FakeRuntime(removal_plan = removal_plan())
    runtime.add_box(observation())

    def fail_removal(_name: str) -> None:
        # Raise the preflight refusal.
        raise NetworkInUse("demo_default", backend = "docker")

    # Substitute the refusing removal call.
    monkeypatch.setattr(runtime, "remove", fail_removal)
    context, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the plan on stdout and the plain refusal on stderr.
    assert result.exit_code == 1
    assert "  demo_default\n" in result.stdout
    assert result.stderr == "Error: Network `demo_default` still has attached `docker` containers.\n"
    assert runtime.inspect("demo") is not None


# Verify an incomplete removal is presented as the project postcondition.
def test_remove_box_reports_an_incomplete_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed a box whose removal violates its postcondition.
    runtime = FakeRuntime(removal_plan = removal_plan())
    runtime.add_box(observation())

    def fail_removal(name: str) -> None:
        # Raise the project postcondition.
        raise IncompleteRemoval("box", name, backend = "docker")

    # Substitute the failing removal call.
    monkeypatch.setattr(runtime, "remove", fail_removal)
    context, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the presenter failure with the command failure class.
    assert result.exit_code == 1
    assert "  demo-workspace-1\n" in result.stdout
    assert result.stderr == "Error: Incomplete removal of `sandbox` project `demo`.\n"


# Verify positive engine statuses survive box removal failures.
def test_remove_box_preserves_engine_failure_status() -> None:
    # Queue one structured engine failure from the removal preview.
    runtime = FakeRuntime()
    runtime.fail_next(
        EngineFailure(
            CommandFailure(
                backend = "docker",
                operation = "remove",
                command = ("docker", "compose", "-p", "demo", "down"),
                exit_code = 125,
                diagnostic = "permission denied",
            ),
        ),
    )
    context, _homes, _buffer = make_context(runtime)
    result: Result = invoke(["remove", "box", "demo", "--yes"], context)

    # Require the positive status, empty stdout, and the single plain presenter.
    assert result.exit_code == 125
    assert result.stdout == ""
    assert result.stderr == "Error: `docker compose -p demo down` failed with exit code 125: permission denied.\n"


# Verify removal progress is transient stderr on a TTY and absent under a pipe.
def test_remove_box_progress_is_tty_only() -> None:
    # Remove a box on a TTY and inspect the transient stream.
    runtime = FakeRuntime(removal_plan = removal_plan())
    runtime.add_box(observation())
    tty_context, _homes, tty_buffer = make_context(runtime, tty = True)
    removed: Result = invoke(["remove", "box", "demo", "--yes"], tty_context)

    # Require the SDK phase on stderr and the success result on stdout.
    assert removed.exit_code == 0, removed.stderr
    assert "Removing box `demo`" in strip_ansi(tty_buffer.getvalue())
    assert "Removing box" not in removed.stdout
    assert "Removing resources for project" in removed.stdout

    # Require no transient bytes under a pipe.
    pipe_runtime = FakeRuntime(removal_plan = removal_plan())
    pipe_runtime.add_box(observation())
    pipe_context, _homes, pipe_buffer = make_context(pipe_runtime)
    piped: Result = invoke(["remove", "box", "demo", "--yes"], pipe_context)
    assert piped.exit_code == 0, piped.stderr
    assert pipe_buffer.getvalue() == ""


# Verify help is Click-owned and constructs no client.
def test_remove_box_help_constructs_no_client() -> None:
    # Fail the test if help constructs a client.
    def fail(_home: Path) -> SandboxClient:
        # Throw a programming failure when help probed the SDK.
        raise AssertionError("help must not construct a client.")

    # Build the inert context once.
    context: CliContext = CliContext(client_factory = FunctionClientFactory(fail))

    # Require the preserved argument and confirmation option help.
    help_result: Result = invoke(["remove", "box", "--help"], context)
    assert help_result.exit_code == 0, help_result.stderr
    assert "The name of the project whose box to remove." in help_result.stdout
    assert "-y, --yes" in help_result.stdout
    assert "Skip the removal confirmation prompt." in help_result.stdout
    assert help_result.stderr == ""

    # Require the remove group to list the new command and keep its siblings.
    group_help: Result = invoke(["remove", "--help"], context)
    assert group_help.exit_code == 0, group_help.stderr
    for command in ("box", "catalogue", "secret", "volume"):
        assert command in group_help.stdout


# Verify `remove box` completes every managed project through the new root.
def test_remove_box_completes_all_projects() -> None:
    # Seed boxes with different states.
    runtime = FakeRuntime()
    runtime.add_box(observation("running", state = BoxState.RUNNING))
    runtime.add_box(observation("stopped", state = BoxState.STOPPED))
    runtime.add_box(observation("fresh", state = BoxState.CREATED))
    context, _homes, _buffer = make_context(runtime)

    # Request completion for the project argument.
    words: str = "sandbox remove box "
    index: int = len(words.split()) - (0 if words.endswith(" ") else 1)
    result: Result = invoke(
        [],
        context,
        env = {
            "_SANDBOX_COMPLETE": "bash_complete",
            "COMP_WORDS": words,
            "COMP_CWORD": str(index),
        },
    )

    # Require every managed project and no failure output.
    assert result.exit_code == 0, result.output
    completed: set[str] = {
        line.split(",", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("plain,")
    }
    assert completed == {"running", "stopped", "fresh"}


# Allow the focused tests to run directly.
if __name__ == "__main__":
    pytest.main([__file__])
