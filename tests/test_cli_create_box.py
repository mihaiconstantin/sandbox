"""Verify the SDK-backed `create box` command."""

# Imports.
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from rich.console import Console

# Import the CLI group, context, and presentation.
from sandbox.cli.commands import boxes as create_box_module
from sandbox.cli.context import CliContext
from sandbox.cli.group import cli
from sandbox.cli.presentation.console import CliPresentation
from sandbox.cli.presentation.errors import ErrorPresenter
from sandbox.cli.presentation.text import strip_ansi
from sandbox.cli.presentation.vocabulary import RuntimeVocabulary

# Import the public SDK.
from sandbox.sdk import SandboxClient

# Import neutral output values and the fake ports.
from sandbox.ports.output import OutputChannel
from sandbox.testing.builder import FakeBuilder
from sandbox.testing.runtime import FakeRuntime

# Import typed failures.
from sandbox.errors.base import CommandFailure
from sandbox.errors.build import BuildFailed
from sandbox.errors.volumes import VolumeOwnershipError

# Import the catalogue fixtures.
from sdk_fixtures import FunctionClientFactory, write_catalogue

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
def make_context(
    runtime: FakeRuntime | None = None,
    builder: FakeBuilder | None = None,
    *,
    tty: bool = False,
) -> tuple[CliContext, FakeRuntime, FakeBuilder, list[Path], list[SandboxClient], io.StringIO]:
    # Resolve the fake ports.
    selected_runtime: FakeRuntime = runtime if runtime is not None else FakeRuntime()
    selected_builder: FakeBuilder = builder if builder is not None else FakeBuilder()

    # Capture the presentation and record the client bindings.
    presentation, buffer = make_presentation(tty = tty)
    homes: list[Path] = []
    clients: list[SandboxClient] = []

    # Build one client per requested home with the presentation sink.
    def factory(home: Path) -> SandboxClient:
        # Record the home and the constructed client.
        homes.append(home)
        client = SandboxClient(home = home, runtime = selected_runtime, builder = selected_builder, output = presentation.output)
        clients.append(client)
        return client

    # Build the injected CLI context with the Click-owned presenter.
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Return the context and its observable facts.
    return context, selected_runtime, selected_builder, homes, clients, buffer


# Invoke the complete command tree with the injected context.
def invoke(args: list[str], context: CliContext, *, input: str | None = None) -> Result:
    # Run the command tree without mixing the streams.
    return CliRunner().invoke(cli, args, obj = context, input = input, prog_name = "sandbox")


# Create one registered catalogue, home, and project directory.
def prepare_home(tmp_path: Path, *, volume: bool = True, secret: bool = False) -> tuple[Path, Path]:
    # Create the configuration home and register the catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    write_catalogue(home, volume = volume, secret = secret)

    # Create the project directory.
    project: Path = tmp_path / "project"
    project.mkdir()
    return home, project


# Replace the generated-directory source with a recording temporary path.
def record_generated_directories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[Path]:
    # Retain the real implementation and record each generated directory.
    real_mkdtemp = tempfile.mkdtemp
    created: list[Path] = []

    # Generate recorded directories below the test root.
    def fake_mkdtemp(*, prefix: str) -> str:
        # Create and record one generated directory.
        path = Path(real_mkdtemp(prefix = prefix, dir = tmp_path))
        created.append(path)
        return str(path)

    # Replace the command's temporary-directory source.
    monkeypatch.setattr(create_box_module.tempfile, "mkdtemp", fake_mkdtemp)
    return created


# Verify a successful create forwards its request and reports the effective recipe.
def test_create_box_succeeds_and_reports_the_effective_recipe(tmp_path: Path) -> None:
    # Prepare the home catalogue and project.
    home, project = prepare_home(tmp_path)
    context, runtime, builder, homes, _clients, _buffer = make_context()

    # Create the box through the complete command tree.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require the preserved success message on stdout and no pipe progress.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Successfully created a box with recipe `base` for the project `demo`.\n"
    assert result.stderr == ""

    # Require the resolved project, catalogue selection, and image request.
    assert runtime.prepare_requests[0].plan.project.directory == project.resolve()
    assert runtime.prepare_requests[0].definition.catalogue == "default"
    assert runtime.prepare_requests[0].definition.recipe == "base"
    assert builder.requests[0].plan.project.name == "demo"
    assert builder.requests[0].rebuild is False

    # Require the volume, initialization, and create flow.
    assert runtime.ensure_volume_requests == ["example-state"]
    assert runtime.initialization_requests[0].artifact.reference == "sandbox/demo:latest"
    assert len(runtime.create_requests) == 1
    assert homes == [home]


# Verify recipe selection and defaulting keep their documented behavior.
def test_create_box_forwards_recipe_selection(tmp_path: Path) -> None:
    # Add a second selectable recipe to the registered catalogue.
    home, project = prepare_home(tmp_path)
    manifest: Path = home / "catalogues" / "default" / "catalogue.toml"
    manifest.write_text(
        manifest.read_text(encoding = "utf-8") + '\n[recipes.alt]\ncompose = "compose.yaml"\nservice = "workspace"\n',
        encoding = "utf-8",
    )
    context, runtime, _builder, _homes, _clients, _buffer = make_context()

    # Create the selected recipe.
    result: Result = invoke(
        [
            "create", "box", "demo",
            "--project-dir", str(project),
            "--home", str(home),
            "--catalogue", "default",
            "--recipe", "alt",
        ],
        context,
    )

    # Require the selected recipe to cross the SDK and appear in the success message.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Successfully created a box with recipe `alt` for the project `demo`.\n"
    assert runtime.prepare_requests[0].definition.recipe == "alt"


# Verify the default rebuild intent and the `--build` request.
def test_create_box_forwards_the_build_request(tmp_path: Path) -> None:
    # Prepare one shared home and fake ports across both invocations.
    home, project = prepare_home(tmp_path)
    context, _runtime, builder, _homes, _clients, _buffer = make_context()
    arguments: list[str] = ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"]

    # Require the default create to reuse an existing image.
    default: Result = invoke(arguments, context)
    assert default.exit_code == 0, default.stderr
    assert builder.requests[0].rebuild is False

    # Require `--build` to forward the rebuild intent.
    rebuilt: Result = invoke([*arguments, "--build"], context)
    assert rebuilt.exit_code == 0, rebuilt.stderr
    assert builder.requests[1].rebuild is True


# Verify a missing secret prompts for a readable file, binds it, and retries creation.
def test_missing_secret_prompts_binds_and_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a recipe requiring one unbound secret and a readable host file.
    home, project = prepare_home(tmp_path, volume = False, secret = True)
    secret_file: Path = tmp_path / "example-secret"
    secret_file.write_text("unique-secret-content\n", encoding = "utf-8")
    context, runtime, builder, _homes, clients, buffer = make_context(tty = True)

    # Select the interactive path and supply an unreadable path before the valid one.
    monkeypatch.setattr(create_box_module, "is_interactive", lambda: True)
    missing_file: Path = tmp_path / "missing-secret"
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
        input = f"{missing_file}\n{secret_file}\n",
    )

    # Require the preserved prompts, warning, save note, and success message.
    assert result.exit_code == 0, result.stderr
    assert "Secret `example-secret` in catalogue `default` is required by recipe `base`." in result.stdout
    assert "It will be mounted read-only at `/run/secrets/example-secret`." in result.stdout
    assert f"Secret file `{missing_file}` does not exist or is not readable." in result.stdout
    assert "Path to secret file:" in result.stdout
    assert "Saved secret `example-secret` in catalogue `default`." in result.stdout
    assert "Successfully created a box with recipe `base` for the project `demo`." in result.stdout

    # Require the catalog-scoped binding and one create attempt after the retry.
    binding = clients[0].secrets.get("default", "example-secret")
    assert binding is not None
    assert binding.host_path == secret_file.resolve()
    assert len(runtime.prepare_requests) == 1
    assert len(builder.requests) == 1

    # Require the secret contents never to enter either output stream.
    assert "unique-secret-content" not in result.stdout
    assert "unique-secret-content" not in result.stderr
    assert "unique-secret-content" not in buffer.getvalue()


# Verify a non-interactive missing secret fails with the actionable hint and cleans the generated workspace.
def test_missing_secret_without_a_terminal_prints_the_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a recipe requiring one unbound secret.
    home, _project = prepare_home(tmp_path, volume = False, secret = True)
    context, runtime, builder, _homes, _clients, _buffer = make_context()
    created: list[Path] = record_generated_directories(monkeypatch, tmp_path)

    # Create without an explicit project directory or terminal.
    result: Result = invoke(["create", "box", "demo", "--home", str(home), "--catalogue", "default"], context)

    # Require the preserved hint on stderr and the generic failure class.
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "Error: Secret `example-secret` is not configured. "
        "Recipe `base` requires it. "
        f"Run `sb create secret example-secret --file <path> --catalogue default --home {home.resolve()}`.\n"
    )

    # Require no port work and no leaked generated directory.
    assert runtime.prepare_requests == []
    assert builder.requests == []
    assert created and not created[0].exists()


# Verify the hint omits a home that matches the default.
def test_missing_secret_hint_omits_the_default_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prepare the default home under a controlled user directory.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    home: Path = tmp_path / ".sandbox"
    home.mkdir()
    write_catalogue(home, volume = False, secret = True)
    project: Path = tmp_path / "project"
    project.mkdir()
    context, _runtime, _builder, _homes, _clients, _buffer = make_context()

    # Create with the default home spelled explicitly and without a terminal.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require the hint without a redundant home option.
    assert result.exit_code == 1
    assert "catalogue default`." in result.stderr
    assert "--home" not in result.stderr


# Verify a failed create retains a user-supplied workspace.
def test_create_box_retains_a_user_supplied_workspace_on_failure(tmp_path: Path) -> None:
    # Prepare a recipe requiring one unbound secret.
    home, project = prepare_home(tmp_path, volume = False, secret = True)
    context, _runtime, _builder, _homes, _clients, _buffer = make_context()

    # Create with the user-supplied project directory.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require the workspace to survive the failure.
    assert result.exit_code == 1
    assert project.is_dir()


# Verify a generated workspace is retained when work left content behind.
def test_create_box_retains_a_nonempty_generated_workspace_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prepare a builder that writes into the workspace before failing.
    home, _project = prepare_home(tmp_path)
    created: list[Path] = record_generated_directories(monkeypatch, tmp_path)

    class WorkspaceWritingBuilder(FakeBuilder):
        # Write a partial artifact and fail the build.
        def prepare(self, plan, definition, requirement, **options):
            # Leave a marker in the generated workspace.
            (plan.workspace.host_directory / "partial.txt").write_text("partial\n", encoding = "utf-8")

            # Fail with a neutral build failure.
            raise BuildFailed(CommandFailure(backend = "docker", operation = "build", command = ("docker", "build"), exit_code = 1, diagnostic = "boom"))

    context, _runtime, _builder, _homes, _clients, _buffer = make_context(builder = WorkspaceWritingBuilder())

    # Create with the generated project directory.
    result: Result = invoke(["create", "box", "demo", "--home", str(home), "--catalogue", "default"], context)

    # Require the non-empty generated workspace to survive.
    assert result.exit_code == 1
    assert created and created[0].is_dir()
    assert (created[0] / "partial.txt").read_text(encoding = "utf-8") == "partial\n"


# Verify a build failure preserves its status, stderr, and build-before-volume ordering.
def test_build_failure_preserves_status_and_creates_no_volume(tmp_path: Path) -> None:
    # Queue one structured build failure with a positive command status.
    home, project = prepare_home(tmp_path)
    builder = FakeBuilder()
    builder.fail_next(
        BuildFailed(
            CommandFailure(
                backend = "docker",
                operation = "build",
                command = ("docker", "build", "sandbox/demo:latest"),
                exit_code = 125,
                diagnostic = "boom",
            )
        )
    )
    context, runtime, _builder, _homes, _clients, _buffer = make_context(builder = builder)

    # Create through the command.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require the preserved command status and plain presenter frame.
    assert result.exit_code == 125
    assert result.stdout == ""
    assert result.stderr == "Error: `docker build sandbox/demo:latest` failed with exit code 125: boom.\n"

    # Require no volume or create mutation after the build failure.
    assert runtime.ensure_volume_requests == []
    assert runtime.create_requests == []


# Verify the root policy and volume ownership failures cross as typed presented errors.
def test_create_box_presents_root_and_volume_policy_failures(tmp_path: Path) -> None:
    # Fail the root policy after the image and volume work.
    home, project = prepare_home(tmp_path)
    root_context, root_runtime, _root_builder, _homes, _clients, _buffer = make_context(runtime = FakeRuntime(uid = 0))
    root: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        root_context,
    )

    # Require the typed root failure and no create.
    assert root.exit_code == 1
    assert root.stdout == ""
    assert root.stderr == "Error: user: Root execution requires `allow_root = true` in the selected recipe.\n"
    assert root_runtime.ensure_volume_requests == ["example-state"]
    assert root_runtime.create_requests == []

    # Refuse an unmanaged volume through the SDK and single presenter.
    class UnmanagedRuntime(FakeRuntime):
        # Reject ownership of the declared volume.
        def ensure_volume(self, name: str):
            # Throw the typed ownership failure.
            raise VolumeOwnershipError(name)

    unmanaged_context, unmanaged_runtime, _unmanaged_builder, _homes, _clients, _buffer = make_context(runtime = UnmanagedRuntime())
    unmanaged: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        unmanaged_context,
    )

    # Require the presented ownership refusal before create.
    assert unmanaged.exit_code == 1
    assert unmanaged.stdout == ""
    assert unmanaged.stderr == "Error: Cannot verify `sandbox` ownership of volume `example-state`.\n"
    assert unmanaged_runtime.create_requests == []


# Verify TTY progress stays on stderr while success and raw child output keep their channels.
def test_create_box_streams_tty_progress_and_child_output(tmp_path: Path) -> None:
    # Emit child output from the runtime create.
    home, project = prepare_home(tmp_path)
    runtime = FakeRuntime(create_output = ((OutputChannel.STDERR, b"\x1b[31mchild\x1b[0m\n"),))
    context, _runtime, _builder, _homes, _clients, buffer = make_context(runtime = runtime, tty = True)

    # Create on a terminal.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require progress and raw child bytes only on stderr.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Successfully created a box with recipe `base` for the project `demo`.\n"
    rendered: str = strip_ansi(buffer.getvalue())
    assert "Preparing image" in rendered
    assert "Creating box `demo`" in rendered
    assert "\x1b[31mchild\x1b[0m" in buffer.getvalue()


# Verify a pipe has no transient progress and plain child output.
def test_create_box_pipe_has_plain_child_output_and_no_progress(tmp_path: Path) -> None:
    # Emit channel-remapped child output with ANSI controls.
    home, project = prepare_home(tmp_path)
    runtime = FakeRuntime(create_output = ((OutputChannel.STDOUT, b"\x1b[31mchild\x1b[0m\n"),))
    context, _runtime, _builder, _homes, _clients, buffer = make_context(runtime = runtime)

    # Create under a pipe.
    result: Result = invoke(
        ["create", "box", "demo", "--project-dir", str(project), "--home", str(home), "--catalogue", "default"],
        context,
    )

    # Require stdout results, plain child output on stderr, and no status text.
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "Successfully created a box with recipe `base` for the project `demo`.\n"
    assert buffer.getvalue() == "child\n"
    assert "Preparing" not in buffer.getvalue()
    assert "\x1b" not in buffer.getvalue()


# Verify help and usage failures construct no client and create no temporary directory.
def test_create_box_help_and_usage_have_no_eager_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fail if any help or usage path constructs a client.
    calls: list[Path] = []

    def factory(home: Path) -> SandboxClient:
        # Record the unexpected client construction.
        calls.append(home)
        raise AssertionError("usage paths must not construct a client")

    # Build one context around the failing factory.
    presentation, _buffer = make_presentation()
    context = CliContext(presentation = presentation, errors = ErrorPresenter(DOCKER_VOCABULARY), client_factory = FunctionClientFactory(factory))

    # Fail if any usage path generates a temporary directory.
    monkeypatch.setattr(create_box_module.tempfile, "mkdtemp", lambda **options: pytest.fail("usage paths must not create a temporary directory"))

    # Require the preserved command help.
    help_result: Result = invoke(["create", "box", "--help"], context)
    assert help_result.exit_code == 0, help_result.stderr
    assert "PROJECT" in help_result.stdout
    assert "The name of the project to create a box for." in help_result.stdout
    assert "-d, --project-dir" in help_result.stdout
    assert "a new empty" in help_result.stdout
    assert "temporary" in help_result.stdout
    assert "directory)" in help_result.stdout
    assert "-c, --catalogue" in help_result.stdout
    assert "[required]" in help_result.stdout
    assert "-r, --recipe" in help_result.stdout
    assert "-h, --home" in help_result.stdout
    assert "--build" in help_result.stdout

    # Require the missing required option to be a usage error.
    missing: Result = invoke(["create", "box", "demo"], context)
    assert missing.exit_code == 2
    assert "Missing option" in missing.stderr
    assert "--catalogue" in missing.stderr

    # Require an invalid project identifier to be a usage error.
    invalid: Result = invoke(["create", "box", "Demo", "--catalogue", "default"], context)
    assert invalid.exit_code == 2
    assert calls == []

    # Require an invalid catalogue identifier to be a usage error.
    invalid_catalogue: Result = invoke(["create", "box", "demo", "--catalogue", "Bad"], context)
    assert invalid_catalogue.exit_code == 2
    assert "catalogue" in invalid_catalogue.stderr
    assert calls == []


# Verify the command is registered under the create group.
def test_create_box_is_registered_in_the_create_group() -> None:
    # Request the create group help without any factory.
    result: Result = CliRunner().invoke(cli, ["create", "--help"], prog_name = "sandbox")

    # Require the box command among the create resources.
    assert result.exit_code == 0, result.stderr
    assert "box" in result.stdout


# Verify a successful generated workspace is retained.
def test_create_box_retains_a_nonempty_generated_workspace_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Record the generated directory.
    home, _project = prepare_home(tmp_path)
    created: list[Path] = record_generated_directories(monkeypatch, tmp_path)
    context, runtime, _builder, _homes, _clients, _buffer = make_context()

    # Create without an explicit project directory.
    result: Result = invoke(["create", "box", "demo", "--home", str(home), "--catalogue", "default"], context)

    # Require the generated directory to exist and be used by the plan.
    assert result.exit_code == 0, result.stderr
    assert created and created[0].is_dir()
    assert runtime.prepare_requests[0].plan.project.directory == created[0].resolve()
    assert list(created[0].iterdir()) == []


# Allow the focused tests to run directly.
if __name__ == "__main__":
    # Run pytest for this file.
    raise SystemExit(pytest.main([__file__]))
