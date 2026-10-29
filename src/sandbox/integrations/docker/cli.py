# Imports.
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# Import the public error values raised by the gateway.
from sandbox.errors.base import CommandFailure
from sandbox.errors.engine import EngineFailure, EngineOutputInvalid
from sandbox.errors.prerequisites import PrerequisiteError, PrerequisiteKind

# Import the process seam and its result value.
from sandbox.integrations.docker.command import CommandResult, CommandRunner

# Import the neutral output contract.
from sandbox.ports.output import SILENT, OutputSink


# Run Docker CLI commands and translate their failures once.
class DockerCli:
    # Construct the gateway around one process runner.
    def __init__(self, runner: CommandRunner) -> None:
        # Record the injected runner.
        self._runner: CommandRunner = runner

    # Run one command without translating a non-zero status.
    def run(
        self,
        arguments: Sequence[str],
        *,
        operation: str,
        environment: Mapping[str, str] | None = None,
        capture: bool = True,
        output: OutputSink = SILENT,
    ) -> CommandResult:
        # Normalize the argument vector.
        command: tuple[str, ...] = tuple(arguments)

        # Execute through the injected runner.
        try:
            # Run the child with the requested capture and output behavior.
            return self._runner.run(command, environment = environment, capture = capture, output = output)

        # A missing or unusable executable is a lazy host prerequisite, not an engine failure.
        except (FileNotFoundError, PermissionError, OSError) as error:
            # Choose the prerequisite kind from the OS failure.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Translate the host failure without leaking the raw exception.
            raise PrerequisiteError(
                "docker",
                kind,
                operation = operation,
                diagnostic = str(error)[:4096],
                hint = "Install Docker and ensure the `docker` executable is available on PATH.",
            ) from error

    # Run one interactive command with inherited standard streams.
    def run_interactive(
        self,
        arguments: Sequence[str],
        *,
        operation: str,
        environment: Mapping[str, str] | None = None,
    ) -> CommandResult:
        # Execute through the injected runner with inherited streams.
        try:
            # Preserve the terminal and the child status unchanged.
            return self._runner.run_interactive(tuple(arguments), environment = environment)

        # Translate a missing executable once.
        except (FileNotFoundError, PermissionError, OSError) as error:
            # Choose the prerequisite kind from the OS failure.
            kind: PrerequisiteKind = PrerequisiteKind.MISSING if isinstance(error, FileNotFoundError) else PrerequisiteKind.UNUSABLE

            # Translate the host failure without leaking the raw exception.
            raise PrerequisiteError("docker", kind, operation = operation, diagnostic = str(error)[:4096]) from error

    # Build the structured command failure for one completed command.
    def failure(self, operation: str, arguments: Sequence[str], result: CommandResult) -> CommandFailure:
        # Preserve a positive engine status and normalize signal termination.
        exit_code: int = result.returncode if result.returncode > 0 else 1

        # Return the bounded neutral failure facts.
        return CommandFailure(
            backend = "docker",
            operation = operation,
            command = tuple(arguments),
            exit_code = exit_code,
            diagnostic = result.diagnostic,
        )

    # Report whether one image is available locally for the selected platform.
    def image_exists(self, reference: str, *, platform: str | None, operation: str) -> bool:
        # Start the local image inspection.
        arguments: list[str] = ["docker", "image", "inspect"]

        # Select the same image platform that the build uses.
        if platform:
            # Retain Docker's own multi-platform selection.
            arguments.extend(["--platform", platform])

        # Request only the image identifier to keep the result small.
        arguments.extend(["--format", "{{.Id}}", reference])

        # Inspect the image without treating a missing image as a command failure.
        result: CommandResult = self.run(arguments, operation = operation)

        # If the image is available locally, the inspection succeeds.
        if result.returncode == 0:
            # Report the image presence.
            return True

        # Read the diagnostic from both streams because Docker versions differ.
        detail: str = f"{result.stdout.decode('utf-8', errors = 'replace')}\n{result.stderr.decode('utf-8', errors = 'replace')}".lower()

        # If the image is missing or unavailable for the selected platform, report absence.
        if (
            "no such image" in detail
            or "no such object" in detail
            or "does not match the specified platform" in detail
        ):
            # Request the caller to prepare the image.
            return False

        # Otherwise, preserve the inspection failure for the caller.
        raise EngineFailure(self.failure(operation, arguments, result))

    # Inspect one image and return its first structured payload.
    def inspect_image(self, reference: str, *, platform: str | None, operation: str) -> Mapping[str, Any]:
        # Start the image inspection.
        arguments: list[str] = ["docker", "image", "inspect"]

        # Select the effective platform when one is known.
        if platform:
            # Add the platform selector.
            arguments.extend(["--platform", platform])

        # Inspect the exact reference.
        arguments.append(reference)

        # Run the inspection and require success.
        result: CommandResult = self.run(arguments, operation = operation)

        # Translate an inspection failure.
        if result.returncode != 0:
            # Throw the neutral engine failure.
            raise EngineFailure(self.failure(operation, arguments, result))

        # Parse the complete inspection payload.
        return self._inspection(operation, result)

    # Read the effective image platform as `os/arch[/variant]`.
    def image_platform(self, inspection: Mapping[str, Any]) -> str | None:
        # Read the operating system and architecture fields.
        os_name: Any = inspection.get("Os")
        architecture: Any = inspection.get("Architecture")
        variant: Any = inspection.get("Variant")

        # Require two usable components.
        if not isinstance(os_name, str) or not os_name or not isinstance(architecture, str) or not architecture:
            # Report an unknown platform.
            return None

        # Include the variant only when Docker reports one.
        if isinstance(variant, str) and variant:
            # Return the complete platform.
            return f"{os_name}/{architecture}/{variant}"

        # Return the base platform.
        return f"{os_name}/{architecture}"

    # Pull one image for the effective platform and stream its progress.
    def pull_image(
        self,
        reference: str,
        *,
        platform: str | None,
        operation: str,
        environment: Mapping[str, str],
        output: OutputSink,
    ) -> CommandResult:
        # Start the pull command.
        arguments: list[str] = ["docker", "pull"]

        # Select the effective platform when one is known.
        if platform:
            # Add the platform selector.
            arguments.extend(["--platform", platform])

        # Name the image last.
        arguments.append(reference)

        # Stream the pull progress with a bounded diagnostic tail.
        return self.run(arguments, operation = operation, environment = environment, capture = False, output = output)

    # Save exactly one target image into an uncompressed Docker archive.
    def save_image(self, reference: str, *, platform: str | None, destination: Path, operation: str) -> CommandResult:
        # Start the image save command.
        arguments: list[str] = ["docker", "image", "save"]

        # Select the target platform before writing the archive.
        if platform:
            # Add the platform selector.
            arguments.extend(["--platform", platform])

        # Write the archive directly to the operation-scoped destination.
        arguments.extend(["--output", str(destination)])

        # Name the single target image last and never add build dependencies.
        arguments.append(reference)

        # Run the export with captured output.
        return self.run(arguments, operation = operation)

    # Start one existing container.
    def start_container(self, identifier: str, *, operation: str) -> None:
        # Start the exact container.
        self._run(operation, ["docker", "start", identifier])

    # Stop one existing container.
    def stop_container(self, identifier: str, *, operation: str) -> None:
        # Stop the exact container with the engine's default timeout.
        self._run(operation, ["docker", "stop", identifier])

    # Remove one existing container without forcing or removing volumes.
    def remove_container(self, identifier: str, *, operation: str) -> None:
        # Remove the exact container.
        self._run(operation, ["docker", "rm", identifier])

    # Remove one existing network.
    def remove_network(self, identifier: str, *, operation: str) -> None:
        # Remove the exact network.
        self._run(operation, ["docker", "network", "rm", identifier])

    # Create one physical volume with the supplied labels.
    def create_volume(self, name: str, labels: Mapping[str, str], *, operation: str) -> CommandResult:
        # Start the volume creation command.
        arguments: list[str] = ["docker", "volume", "create"]

        # Add every ownership label in insertion order.
        for key, value in labels.items():
            # Add the exact label.
            arguments.extend(["--label", f"{key}={value}"])

        # Name the physical volume last.
        arguments.append(name)

        # Return the raw result so the runtime can translate creation failures.
        return self.run(arguments, operation = operation)

    # Remove one physical volume without forcing deletion.
    def remove_volume(self, name: str, *, operation: str) -> None:
        # Remove the exact volume.
        self._run(operation, ["docker", "volume", "rm", name])

    # Run one interactive shell in a container and return its raw status.
    def exec_interactive(self, identifier: str, shell: str, login: bool, *, operation: str) -> CommandResult:
        # Build the interactive exec command.
        arguments: list[str] = ["docker", "exec", "-it", identifier, shell]

        # Append the login-shell flag when requested.
        if login:
            # Add the login-shell flag after the shell.
            arguments.append("-l")

        # Run the shell with inherited standard streams and no success check.
        return self.run_interactive(arguments, operation = operation)

    # Run one command that must succeed.
    def _run(self, operation: str, arguments: Sequence[str]) -> CommandResult:
        # Execute the command through the injected runner.
        result: CommandResult = self.run(arguments, operation = operation)

        # If the command failed.
        if result.returncode != 0:
            # Translate the engine failure once.
            raise EngineFailure(self.failure(operation, arguments, result))

        # Return the successful result.
        return result

    # Inspect one resource and parse its first payload.
    def _inspect_payload(self, operation: str, arguments: Sequence[str]) -> Mapping[str, Any]:
        # Require the inspection to succeed.
        result: CommandResult = self._run(operation, arguments)

        # Parse the inspection payload.
        return self._inspection(operation, result)

    # Split one identifier listing.
    def _lines(self, stdout: bytes) -> tuple[str, ...]:
        # Decode invalid partial UTF-8 without raising across the boundary.
        text: str = stdout.decode("utf-8", errors = "replace")

        # Return the nonempty lines in engine order.
        return tuple(line for line in text.splitlines() if line)

    # Parse one nonempty image inspection array.
    def _inspection(self, operation: str, result: CommandResult) -> Mapping[str, Any]:
        # Parse the JSON array.
        try:
            # Parse the complete output.
            payload: Any = json.loads(result.stdout)

        # If the output is not JSON.
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            # Translate the malformed response without leaking the parser error.
            raise EngineOutputInvalid("docker", operation, result.stdout[:200].decode("utf-8", errors = "replace")) from error

        # Require a nonempty array of objects.
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], Mapping):
            # Throw.
            raise EngineOutputInvalid("docker", operation, result.stdout[:200].decode("utf-8", errors = "replace"))

        # Return the first inspected image.
        return payload[0]


# Define the public API of the Docker CLI gateway.
__all__: list[str] = ["DockerCli"]
