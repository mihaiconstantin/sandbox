"""Answer Docker and Compose runtime commands from deterministic scripted state."""

# Imports.
import copy
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import the command result contract and output values.
from sandbox.ports.output import SILENT, OutputChannel

# Import the scripted result type used by the integration seam.
from sandbox.integrations.docker.command import CommandResult

# Match one JSON-quoted override scalar.
_QUOTED = re.compile(r'^"(.*)"$')

# Match the generated pre-start hook line.
_PRE_START = re.compile(r"^        pre_start: !override (.+)$")


# Record one command received by the scripted engine.
@dataclass(frozen = True, slots = True)
class RecordedCommand:
    # Record the argument vector.
    arguments: tuple[str, ...]

    # Record the environment supplied by the integration.
    environment: Mapping[str, str] | None

    # Report whether complete output was requested.
    capture: bool


# Record the override effects parsed from one rendered override document.
@dataclass(frozen = True, slots = True)
class ParsedOverride:
    # Record the service labels.
    labels: dict[str, str]

    # Record the service working directory.
    working_dir: str | None

    # Record the service mounts.
    mounts: list[dict[str, Any]]

    # Record the service secret aliases.
    secrets: list[str]

    # Record the replaced pre-start hook sequence.
    pre_start: list[dict[str, Any]] | None

    # Record the external volume names.
    volume_names: list[str]

    # Record the top-level secret file declarations.
    secret_files: dict[str, str]

    # Record the default network labels.
    network_labels: dict[str, str]


# Answer Docker and Compose commands from deterministic scripted state.
class ScriptedComposeEngine:
    # Construct an engine with one recipe service configuration.
    def __init__(self, *, project: str = "demo", service: str = "workspace") -> None:
        # Record the fixture identity.
        self.project: str = project
        self.service: str = service

        # Record every command in order.
        self.commands: list[RecordedCommand] = []

        # Record every override document read during a command.
        self.override_texts: list[str] = []

        # Record the scripted recipe configuration.
        self.base_configuration: dict[str, Any] = {
            "services": {
                service: {
                    "image": "sandbox/contract:latest",
                },
            },
            "networks": {"default": {}},
        }

        # Record the Compose and engine responses.
        self.compose_version: bytes = b"5.6.0\n"
        self.compose_returncode: int = 0
        self.compose_stderr: bytes = b""
        self.config_returncode: int = 0
        self.config_stderr: bytes = b""
        self.invalid_config: bool = False
        self.up_returncode: int = 0
        self.up_stderr: bytes = b""
        self.up_output: bytes = b"creating\n"
        self.create_no_container: bool = False

        # Record the UID probe response.
        self.probe_output: bytes = b"1000\n"
        self.probe_returncode: int = 0
        self.probe_stderr: bytes = b""

        # Record the interactive shell status.
        self.enter_status: int = 0

        # Record the image facts.
        self.image_available: bool = True
        self.operating_system: str = "linux"
        self.architecture: str = "amd64"
        self.variant: str | None = None
        self.healthcheck: Any = None

        # Record the volume responses.
        self.volume_create_returncode: int = 0
        self.volume_create_stderr: bytes = b""
        self.drop_volume_create: bool = False
        self.keep_volume_after_remove: bool = False
        self.volume_remove_returncode: int = 0

        # Record the lifecycle responses.
        self.start_returncode: int = 0
        self.stop_returncode: int = 0
        self.remove_returncode: int = 0
        self.network_remove_returncode: int = 0
        self.keep_container_after_remove: bool = False
        self.keep_network_after_remove: bool = False

        # Record the override-application switches.
        self.apply_override_labels: bool = True
        self.apply_working_dir: bool = True
        self.apply_mounts: bool = True
        self.apply_secrets: bool = True
        self.apply_network_labels: bool = True

        # Record deterministic mutation hooks for verification tests.
        self.mutate_on_final: dict[str, Any] | None = None
        self.mutate_configuration_on_final: dict[str, Any] | None = None

        # Record the engine state.
        self.volumes: dict[str, dict[str, Any]] = {}
        self.containers: dict[str, dict[str, Any]] = {}
        self.networks: dict[str, dict[str, Any]] = {}
        self._container_counter: int = 0
        self._network_counter: int = 0

    # Read the effective service image reference.
    @property
    def image(self) -> str:
        # Return the configured image or the Compose default.
        service: Mapping[str, Any] = self.base_configuration.get("services", {}).get(self.service, {})
        return service.get("image") or f"{self.project}-{self.service}"

    # Add one volume to the scripted engine.
    def add_volume(
        self,
        name: str,
        *,
        labels: Mapping[str, str] | None = None,
        driver: str = "local",
        options: Mapping[str, str] | None = None,
        mountpoint: str | None = None,
    ) -> None:
        # Record the volume payload.
        self.volumes[name] = {
            "Name": name,
            "Driver": driver,
            "Mountpoint": mountpoint or f"/var/lib/docker/volumes/{name}/_data",
            "Labels": dict(labels or {}),
            "Options": None if options is None else dict(options),
        }

    # Add one volume with the full managed labels.
    def add_managed_volume(self, name: str, *, driver: str = "local", options: Mapping[str, str] | None = None) -> None:
        # Record the managed volume.
        self.add_volume(
            name,
            labels = {"sb.managed": "true", "sb.resource": "volume", "sb.scope": "shared"},
            driver = driver,
            options = options,
        )

    # Add one network to the scripted engine.
    def add_network(self, name: str, *, labels: Mapping[str, str] | None = None) -> None:
        # Allocate the identifier.
        self._network_counter += 1

        # Record the network payload.
        self.networks[f"network-{self._network_counter}"] = {
            "Id": f"network-{self._network_counter}",
            "Name": name,
            "Labels": dict(labels or {}),
        }

    # Add one container to the scripted engine.
    def add_container(
        self,
        *,
        labels: Mapping[str, str],
        state: str = "running",
        name: str | None = None,
        image: str | None = None,
        working_dir: str | None = None,
        mounts: Sequence[Mapping[str, Any]] = (),
        networks: Sequence[str] = (),
    ) -> str:
        # Allocate the identifier.
        self._container_counter += 1
        identifier: str = f"container-{self._container_counter}"

        # Record the container payload.
        self.containers[identifier] = {
            "Id": identifier,
            "Name": f"/{name or f'{self.project}-{self.service}-1'}",
            "State": {"Status": state, "Running": state in ("running", "paused", "restarting")},
            "Config": {
                "Image": image or self.image,
                "WorkingDir": working_dir or "",
                "Labels": dict(labels),
            },
            "Mounts": [dict(mount) for mount in mounts],
            "NetworkSettings": {"Networks": {network: {"IPAddress": "172.18.0.2"} for network in networks}},
        }

        # Return the identifier.
        return identifier

    # Run one scripted Docker or Compose command.
    def run(
        self,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        capture: bool = True,
        output: Any = SILENT,
    ) -> CommandResult:
        # Normalize and record the invocation.
        command: tuple[str, ...] = tuple(arguments)
        self.commands.append(RecordedCommand(arguments = command, environment = environment, capture = capture))

        # Answer the Compose version probe.
        if command[:3] == ("docker", "compose", "version"):
            # Return the scripted version response.
            return CommandResult(command, self.compose_returncode, self.compose_version, self.compose_stderr)

        # Answer Compose configuration and start commands.
        if command[:2] == ("docker", "compose"):
            # Resolve the configuration.
            if "config" in command:
                # Read the override applied last.
                override: str | None = self._read_override(command)

                # Return a scripted malformed response.
                if self.invalid_config:
                    # Return a non-JSON body.
                    return CommandResult(command, 0, b"not json", b"")

                # Return a scripted failure.
                if self.config_returncode != 0:
                    # Return the failure.
                    return CommandResult(command, self.config_returncode, b"", self.config_stderr)

                # Build the effective configuration.
                configuration: dict[str, Any] = self._effective_configuration(override)

                # Return the resolved configuration.
                return CommandResult(command, 0, json.dumps(configuration).encode("utf-8"), b"")

            # Start the selected service.
            if "up" in command:
                # Read the override applied last.
                override = self._read_override(command)

                # Emit one deterministic child chunk.
                if self.up_output:
                    # Forward the chunk through the sink.
                    output.process_output(OutputChannel.STDOUT, self.up_output)

                # Return a scripted failure without mutation.
                if self.up_returncode != 0:
                    # Return the failure.
                    return CommandResult(command, self.up_returncode, b"", self.up_stderr)

                # Create the project resources unless the test scripts a missing postcondition.
                if not self.create_no_container:
                    # Record the project container and network.
                    self._create_container(self._effective_configuration(override))

                # Return success.
                return CommandResult(command, 0, b"", b"")

        # Answer image inspections.
        if command[:3] == ("docker", "image", "inspect"):
            # Read the inspected reference.
            reference: str = command[-1]

            # Report absence for a missing image.
            if not self.image_available:
                # Return Docker's missing-image diagnostic.
                return CommandResult(command, 1, b"", f"Error response from daemon: No such image: {reference}".encode("utf-8"))

            # Build the inspection payload.
            payload: dict[str, Any] = {
                "Id": "sha256:config-id",
                "RepoDigests": [f"{reference}@sha256:manifest-digest"],
                "Os": self.operating_system,
                "Architecture": self.architecture,
                "Variant": self.variant,
                "Config": {"Image": reference, "Healthcheck": copy.deepcopy(self.healthcheck)},
            }

            # Return the image identifier for existence probes.
            if "--format" in command:
                # Return only the identifier.
                return CommandResult(command, 0, b"sha256:config-id\n", b"")

            # Return the structured inspection array.
            return CommandResult(command, 0, json.dumps([payload]).encode("utf-8"), b"")

        # Answer the UID probe.
        if command[:2] == ("docker", "run"):
            # Return the scripted probe result.
            return CommandResult(command, self.probe_returncode, self.probe_output, self.probe_stderr)

        # Answer container queries.
        if command[:2] == ("docker", "ps"):
            # Select matching containers.
            identifiers: list[str] = self._matching_containers(command)

            # Return the identifiers.
            return CommandResult(command, 0, ("\n".join(identifiers) + ("\n" if identifiers else "")).encode("utf-8"), b"")

        # Answer direct container inspections and mutations.
        if command[:3] == ("docker", "container", "inspect"):
            # Read the identifier.
            identifier: str = command[-1]

            # Report absence for an unknown container.
            if identifier not in self.containers:
                # Return Docker's missing-container diagnostic.
                return CommandResult(command, 1, b"", f"Error response from daemon: No such container: {identifier}".encode("utf-8"))

            # Return the inspection array.
            return CommandResult(command, 0, json.dumps([self.containers[identifier]]).encode("utf-8"), b"")

        # Answer container lifecycle commands.
        if command[:2] == ("docker", "start"):
            # Read the identifier.
            identifier = command[-1]

            # Read the scripted status.
            if self.start_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.start_returncode, b"", b"start failed\n")

            # Update a known container.
            if identifier in self.containers:
                # Mark the container running.
                self.containers[identifier]["State"] = {"Status": "running", "Running": True}

                # Return success.
                return CommandResult(command, 0, b"", b"")

            # Return the missing-container failure.
            return CommandResult(command, 1, b"", b"No such container\n")

        if command[:2] == ("docker", "stop"):
            # Read the identifier.
            identifier = command[-1]

            # Read the scripted status.
            if self.stop_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.stop_returncode, b"", b"stop failed\n")

            # Update a known container.
            if identifier in self.containers:
                # Mark the container stopped.
                self.containers[identifier]["State"] = {"Status": "exited", "Running": False}

                # Return success.
                return CommandResult(command, 0, b"", b"")

            # Return the missing-container failure.
            return CommandResult(command, 1, b"", b"No such container\n")

        if command[:2] == ("docker", "rm"):
            # Read the identifier.
            identifier = command[-1]

            # Read the scripted status.
            if self.remove_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.remove_returncode, b"", b"remove failed\n")

            # Delete a known container.
            if identifier in self.containers:
                # Remove the container unless the test scripts a failed postcondition.
                if not self.keep_container_after_remove:
                    # Delete the container.
                    del self.containers[identifier]

                # Return success.
                return CommandResult(command, 0, b"", b"")

            # Return the missing-container failure.
            return CommandResult(command, 1, b"", b"No such container\n")

        # Answer interactive exec.
        if command[:3] == ("docker", "exec", "-it"):
            # Return the scripted shell status.
            return CommandResult(command, self.enter_status)

        # Answer network queries and mutations.
        if command[:3] == ("docker", "network", "ls"):
            # Select matching networks.
            identifiers: list[str] = self._matching_networks(command)

            # Return the identifiers.
            return CommandResult(command, 0, ("\n".join(identifiers) + ("\n" if identifiers else "")).encode("utf-8"), b"")

        if command[:3] == ("docker", "network", "inspect"):
            # Read the identifier.
            identifier = command[-1]

            # Report absence for an unknown network.
            if identifier not in self.networks:
                # Return the missing-network diagnostic.
                return CommandResult(command, 1, b"", f"Error response from daemon: network {identifier} not found".encode("utf-8"))

            # Return the inspection array with dynamic attachments.
            payload: dict[str, Any] = copy.deepcopy(self.networks[identifier])
            payload["Containers"] = self._network_attachments(payload["Name"])
            return CommandResult(command, 0, json.dumps([payload]).encode("utf-8"), b"")

        if command[:3] == ("docker", "network", "rm"):
            # Read the identifier.
            identifier = command[-1]

            # Read the scripted status.
            if self.network_remove_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.network_remove_returncode, b"", b"network remove failed\n")

            # Delete the network unless the test scripts a failed postcondition.
            if not self.keep_network_after_remove:
                # Remove the network.
                self.networks.pop(identifier, None)
            return CommandResult(command, 0, b"", b"")

        # Answer volume queries and mutations.
        if command[:3] == ("docker", "volume", "ls"):
            # Return every name in the requested form.
            if "--format" in command:
                # Return all volume names.
                names: list[str] = sorted(self.volumes)

            # Otherwise filter by label.
            else:
                # Select matching volume names.
                names = sorted(name for name, payload in self.volumes.items() if self._labels_match(payload.get("Labels") or {}, command))

            # Return the names.
            return CommandResult(command, 0, ("\n".join(names) + ("\n" if names else "")).encode("utf-8"), b"")

        if command[:3] == ("docker", "volume", "inspect"):
            # Read the name.
            name = command[-1]

            # Report absence for an unknown volume.
            if name not in self.volumes:
                # Return the missing-volume diagnostic.
                return CommandResult(command, 1, b"", f"Error response from daemon: No such volume: {name}".encode("utf-8"))

            # Return the inspection array.
            return CommandResult(command, 0, json.dumps([self.volumes[name]]).encode("utf-8"), b"")

        if command[:3] == ("docker", "volume", "create"):
            # Read the scripted status.
            if self.volume_create_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.volume_create_returncode, b"", self.volume_create_stderr)

            # Read the labels and final name.
            labels: dict[str, str] = {}
            for index, argument in enumerate(command):
                # Read each label pair.
                if argument == "--label" and index + 1 < len(command):
                    # Split the label.
                    key, value = command[index + 1].split("=", 1)
                    labels[key] = value

            # Read the volume name.
            name = command[-1]

            # Record the created volume unless the test scripts an incomplete creation.
            if not self.drop_volume_create and name not in self.volumes:
                # Record the volume.
                self.add_volume(name, labels = labels)

            # Return success.
            return CommandResult(command, 0, b"", b"")

        if command[:3] == ("docker", "volume", "rm"):
            # Read the name.
            name = command[-1]

            # Read the scripted status.
            if self.volume_remove_returncode != 0:
                # Return the failure.
                return CommandResult(command, self.volume_remove_returncode, b"", b"volume remove failed\n")

            # Remove the volume unless the test scripts a failed postcondition.
            if not self.keep_volume_after_remove:
                # Delete the volume.
                self.volumes.pop(name, None)

            # Return success.
            return CommandResult(command, 0, b"", b"")

        # Throw for any unexpected command.
        raise AssertionError(f"Unexpected command: {command}")

    # Run one scripted command with inherited standard streams.
    def run_interactive(self, arguments: Sequence[str], *, environment: Mapping[str, str] | None = None) -> CommandResult:
        # Normalize and record the invocation.
        command: tuple[str, ...] = tuple(arguments)
        self.commands.append(RecordedCommand(arguments = command, environment = environment, capture = False))

        # Answer the interactive shell command.
        if command[:3] == ("docker", "exec", "-it"):
            # Return the scripted shell status.
            return CommandResult(command, self.enter_status)

        # Throw for any unexpected interactive command.
        raise AssertionError(f"Unexpected interactive command: {command}")

    # Read the override document applied last in one command.
    def _read_override(self, command: tuple[str, ...]) -> str | None:
        # For each file argument.
        for index, argument in enumerate(command):
            # If this is a file flag with an override path.
            if argument == "-f" and index + 1 < len(command):
                # Read the path.
                path: Path = Path(command[index + 1])

                # If the path is an operation-scoped override.
                if path.name == "override.yaml":
                    # Read the override text.
                    text: str = path.read_text(encoding = "utf-8")

                    # Record the override.
                    self.override_texts.append(text)

                    # Return the override.
                    return text

        # Report no override.
        return None

    # Build the effective configuration from the base recipe and one override.
    def _effective_configuration(self, override: str | None) -> dict[str, Any]:
        # Copy the recipe configuration.
        configuration: dict[str, Any] = copy.deepcopy(self.base_configuration)

        # Require the selected service.
        services: dict[str, Any] = configuration.setdefault("services", {})
        if self.service not in services:
            # Return the malformed configuration unchanged.
            return configuration

        # Read the selected service.
        service: dict[str, Any] = services[self.service]

        # If no override is applied, return the recipe configuration.
        if override is None:
            # Return the recipe configuration.
            return configuration

        # Parse the override effects.
        parsed: ParsedOverride = self._parse_override(override)

        # Apply the sandbox service labels.
        if self.apply_override_labels and parsed.labels:
            # Merge the labels with the override winning.
            labels: dict[str, str] = dict(service.get("labels") or {})
            labels.update(parsed.labels)
            service["labels"] = labels

        # Apply the working directory.
        if self.apply_working_dir and parsed.working_dir is not None:
            # Set the realized working directory.
            service["working_dir"] = parsed.working_dir

        # Apply the mounts with the override winning by target.
        if self.apply_mounts and parsed.mounts:
            # Merge the mounts by target.
            service["volumes"] = self._merge_mounts(service.get("volumes") or [], parsed.mounts)

        # Apply the service secret references.
        if self.apply_secrets and parsed.secrets:
            # Read the recipe references.
            references: list[str] = self._secret_names(service.get("secrets"))

            # Add the sandbox secrets in order.
            for alias in parsed.secrets:
                # Add a missing reference.
                if alias not in references:
                    # Append the alias.
                    references.append(alias)

            # Record the service references.
            service["secrets"] = [{"source": reference} for reference in references]

        # Apply the top-level secret declarations.
        if self.apply_secrets and parsed.secret_files:
            # Merge the declarations.
            declarations: dict[str, Any] = dict(configuration.get("secrets") or {})
            for alias, path in parsed.secret_files.items():
                # Record the file declaration.
                declarations[alias] = {"file": path}
            configuration["secrets"] = declarations

        # Apply the external volume declarations.
        if self.apply_mounts and parsed.volume_names:
            # Merge the external volume declarations.
            volumes: dict[str, Any] = dict(configuration.get("volumes") or {})
            for name in parsed.volume_names:
                # Record the external volume.
                volumes[name] = {"external": True, "name": name}
            configuration["volumes"] = volumes

        # Apply the default network labels.
        if self.apply_network_labels and parsed.network_labels:
            # Merge the network labels.
            networks: dict[str, Any] = configuration.setdefault("networks", {})
            default: dict[str, Any] = networks.setdefault("default", {})
            labels = dict(default.get("labels") or {})
            labels.update(parsed.network_labels)
            default["labels"] = labels

        # Apply the generated pre-start hook replacement.
        if parsed.pre_start is not None:
            # Replace the complete hook sequence.
            service["pre_start"] = parsed.pre_start

            # Apply any final-resolution mutation used by verification tests.
            if self.mutate_on_final is not None:
                # Mutate the realized service.
                service.update(self.mutate_on_final)

            # Apply any final top-level mutation used by verification tests.
            if self.mutate_configuration_on_final is not None:
                # Mutate the realized configuration.
                configuration.update(self.mutate_configuration_on_final)

        # Return the realized configuration.
        return configuration

    # Parse one rendered override document into its fixed effects.
    def _parse_override(self, text: str) -> ParsedOverride:
        # Split the document into lines.
        lines: list[str] = text.splitlines()

        # Read the service label block.
        labels: dict[str, str] = {}
        for index, line in enumerate(lines):
            # If this is the service label header.
            if line == "        labels:":
                # Read each service label entry.
                for entry in self._block(lines, index, 8):
                    # Split the label pair.
                    name, value = entry.split(":", 1)
                    labels[name.strip()] = self._unquote(value.strip())

                # Stop after the service label block.
                break

        # Read the working directory.
        working_dir: str | None = None
        for line in lines:
            # If this is the service working directory.
            if line.startswith("        working_dir: "):
                # Read the quoted working directory.
                working_dir = self._unquote(line.split(": ", 1)[1])

        # Read the service volume block.
        mounts: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            # If this is the service volume header.
            if line == "        volumes:":
                # Read the mount entries.
                mounts = self._parse_mounts(self._block(lines, index, 8))

        # Read the service secret block.
        secrets: list[str] = []
        for index, line in enumerate(lines):
            # If this is the service secret header.
            if line == "        secrets:":
                # Read each secret alias.
                for entry in self._block(lines, index, 8):
                    # Record the alias.
                    secrets.append(entry.removeprefix("- ").strip())

        # Read the replaced pre-start hook sequence.
        pre_start: list[dict[str, Any]] | None = None
        for line in lines:
            # Match the generated hook line.
            match = _PRE_START.match(line)
            if match is not None:
                # Parse the JSON hook array.
                pre_start = json.loads(match.group(1))

        # Read the top-level volume block.
        volume_names: list[str] = []
        for index, line in enumerate(lines):
            # If this is the top-level volume header.
            if line == "volumes:":
                # Read each volume declaration.
                for entry in self._top_level_entries(lines, index):
                    # Record the physical name.
                    volume_names.append(entry)

        # Read the top-level secret block.
        secret_files: dict[str, str] = {}
        for index, line in enumerate(lines):
            # If this is the top-level secret header.
            if line == "secrets:":
                # Read each declaration.
                for alias in self._top_level_entries(lines, index):
                    # Find the alias header.
                    header: str = f"    {alias}:"
                    for offset, candidate in enumerate(lines):
                        # If this is the alias header.
                        if candidate == header:
                            # Read the file declaration after the alias.
                            file_line: str = lines[offset + 1].strip()
                            secret_files[alias] = self._unquote(file_line.removeprefix("file: "))
                            break

        # Read the top-level default network labels.
        network_labels: dict[str, str] = {}
        for index, line in enumerate(lines):
            # If this is the top-level network header.
            if line == "networks:":
                # Read the default network block.
                block: list[str] = self._block(lines, index, 0)
                for offset, candidate in enumerate(block):
                    # If this is the default network label header.
                    if candidate == "labels:":
                        # Read each label entry until the block ends.
                        for entry in block[offset + 1:]:
                            # Stop at a non-indented entry.
                            if not entry.startswith("sb."):
                                # Leave the label section.
                                break
                            name, value = entry.split(":", 1)
                            network_labels[name.strip()] = self._unquote(value.strip())

        # Return the parsed effects.
        return ParsedOverride(
            labels = labels,
            working_dir = working_dir,
            mounts = mounts,
            secrets = secrets,
            pre_start = pre_start,
            volume_names = volume_names,
            secret_files = secret_files,
            network_labels = network_labels,
        )

    # Read the entries nested under one header line.
    def _block(self, lines: list[str], header: int, indent: int) -> list[str]:
        # Prepare the nested entries.
        entries: list[str] = []

        # For each following line.
        for line in lines[header + 1:]:
            # Stop at the next nonblank line at or above the header indentation.
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                # Leave the block.
                break

            # Record the stripped entry.
            if line.strip():
                # Append the entry.
                entries.append(line.strip())

        # Return the nested entries.
        return entries

    # Read the top-level names nested under one header line.
    def _top_level_entries(self, lines: list[str], header: int) -> list[str]:
        # Prepare the names.
        names: list[str] = []

        # For each following line.
        for line in lines[header + 1:]:
            # Stop at the next nonblank line at or above the header indentation.
            if line.strip() and len(line) - len(line.lstrip()) <= 0:
                # Leave the block.
                break

            # If this is a four-space key line.
            if line.startswith("    ") and not line.startswith("        ") and line.strip().endswith(":"):
                # Read the unquoted key.
                names.append(self._unquote(line.strip().removesuffix(":")))

        # Return the names.
        return names

    # Parse one service volume block.
    def _parse_mounts(self, entries: list[str]) -> list[dict[str, Any]]:
        # Prepare the mounts.
        mounts: list[dict[str, Any]] = []

        # Prepare the current mount.
        current: dict[str, Any] | None = None

        # For each entry.
        for entry in entries:
            # Start a new mount at each entry marker.
            if entry.startswith("- "):
                # Record the previous mount.
                if current is not None:
                    # Append the mount.
                    mounts.append(current)

                # Start a new mount.
                current = {}

                # Read the entry marker body.
                entry = entry[2:]

            # If a mount is open.
            if current is not None:
                # Split the key and value.
                key, value = entry.split(":", 1)

                # Read only the supported mount fields.
                if key.strip() in ("type", "source", "target"):
                    # Record the unquoted field.
                    current[key.strip()] = self._unquote(value.strip())

        # Record the final mount.
        if current is not None:
            # Append the final mount.
            mounts.append(current)

        # Return the mounts.
        return mounts

    # Merge two mount lists with the override winning by target.
    def _merge_mounts(self, base: object, override: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Require a base mount list.
        base_mounts: list[Any] = base if isinstance(base, list) else []

        # Prepare the merged mounts by target.
        merged: dict[str, dict[str, Any]] = {}

        # For each base mount.
        for mount in base_mounts:
            # Require a mapping mount.
            if isinstance(mount, Mapping):
                # Record the mount by target.
                merged[str(mount.get("target"))] = dict(mount)

        # For each override mount.
        for mount in override:
            # Override the mount at the same target.
            merged[str(mount.get("target"))] = dict(mount)

        # Return the merged mounts.
        return list(merged.values())

    # Read secret names from the resolved service forms.
    def _secret_names(self, value: object) -> list[str]:
        # If no secrets are declared, return no names.
        if value is None:
            # Return no names.
            return []

        # Accept a single entry or an array.
        entries: list[object] = value if isinstance(value, list) else [value]

        # Prepare the names.
        names: list[str] = []

        # For each entry.
        for entry in entries:
            # If the entry is a name.
            if isinstance(entry, str):
                # Record the name.
                names.append(entry)

            # If the entry is a mapping.
            elif isinstance(entry, Mapping) and isinstance(entry.get("source"), str):
                # Read and record the source name.
                source: object = entry["source"]
                assert isinstance(source, str)
                names.append(source)

        # Return the names.
        return names

    # Create the project container and network for one realized configuration.
    def _create_container(self, configuration: Mapping[str, Any]) -> None:
        # Read the service configuration.
        service: Mapping[str, Any] = configuration.get("services", {}).get(self.service, {})

        # Read the effective labels.
        labels: dict[str, str] = dict(service.get("labels") or {})

        # Add the Compose identity labels.
        labels["com.docker.compose.project"] = self.project
        labels["com.docker.compose.service"] = self.service
        labels["com.docker.compose.oneoff"] = "False"

        # Build the reported mounts.
        mounts: list[dict[str, Any]] = []
        for entry in service.get("volumes") or []:
            # Require a mapping mount.
            if not isinstance(entry, Mapping):
                continue

            # Record the mount by type.
            if entry.get("type") == "volume":
                mounts.append({"Type": "volume", "Name": entry.get("source"), "Destination": entry.get("target")})
            elif entry.get("type") == "bind":
                mounts.append({"Type": "bind", "Source": entry.get("source"), "Destination": entry.get("target")})

        # Add the secret file binds.
        for alias in self._secret_names(service.get("secrets")):
            # Read the declaration.
            declaration: Mapping[str, Any] = (configuration.get("secrets") or {}).get(alias) or {}

            # Record the read-only file delivery.
            mounts.append({"Type": "bind", "Source": declaration.get("file", ""), "Destination": f"/run/secrets/{alias}"})

        # Read the effective networks.
        network_names: list[str] = list((service.get("networks") or {}).keys()) if isinstance(service.get("networks"), Mapping) else []
        if not network_names and service.get("network_mode") != "host":
            # Select the default network.
            network_names = ["default"]

        # Ensure each network exists.
        for name in network_names:
            # Compose names the physical network after the project.
            physical: str = name if name != "default" else f"{self.project}_default"

            # If the network does not exist.
            if not any(payload.get("Name") == physical for payload in self.networks.values()):
                # Read the default labels.
                network_labels: Mapping[str, str] = (configuration.get("networks", {}).get(name, {}) or {}).get("labels") or {}

                # Add the Compose project label.
                labels_with_project: dict[str, str] = dict(network_labels)
                labels_with_project["com.docker.compose.project"] = self.project

                # Record the network.
                self.add_network(physical, labels = labels_with_project)

        # Record the container.
        self.add_container(
            labels = labels,
            state = "running",
            image = service.get("image") or f"{self.project}-{self.service}",
            working_dir = service.get("working_dir") or "",
            mounts = mounts,
            networks = network_names,
        )

    # Select the container identifiers matching one ps command.
    def _matching_containers(self, command: tuple[str, ...]) -> list[str]:
        # Prepare the matching identifiers.
        identifiers: list[str] = []

        # For each container.
        for identifier, payload in self.containers.items():
            # Read its labels.
            labels: Mapping[str, str] = payload.get("Config", {}).get("Labels") or {}

            # Require label filters to match.
            if not self._labels_match(labels, command):
                # Skip the container.
                continue

            # Require every volume filter to match.
            if not self._volume_filter_matches(payload, command):
                # Skip the container.
                continue

            # Record the identifier.
            identifiers.append(identifier)

        # Return the identifiers.
        return identifiers

    # Select the network identifiers matching one network list command.
    def _matching_networks(self, command: tuple[str, ...]) -> list[str]:
        # Prepare the matching identifiers.
        identifiers: list[str] = []

        # For each network.
        for identifier, payload in self.networks.items():
            # Require label filters to match.
            if not self._labels_match(payload.get("Labels") or {}, command):
                # Skip the network.
                continue

            # Record the identifier.
            identifiers.append(identifier)

        # Return the identifiers.
        return identifiers

    # Report whether every label filter matches one label set.
    def _labels_match(self, labels: Mapping[str, str], command: tuple[str, ...]) -> bool:
        # For each label filter.
        for index, argument in enumerate(command):
            # Read each label filter.
            if argument == "--filter" and index + 1 < len(command):
                # Read the filter expression.
                expression: str = command[index + 1]

                # Ignore non-label filters.
                if not expression.startswith("label="):
                    # Continue to the next filter.
                    continue

                # Split the required label.
                key, value = expression.removeprefix("label=").split("=", 1)

                # If the label does not match.
                if labels.get(key) != value:
                    # Report no match.
                    return False

        # Report a match.
        return True

    # Report whether the volume filter matches one container.
    def _volume_filter_matches(self, payload: Mapping[str, Any], command: tuple[str, ...]) -> bool:
        # For each volume filter.
        for index, argument in enumerate(command):
            # Read each volume filter.
            if argument == "--filter" and index + 1 < len(command):
                # Read the filter expression.
                expression: str = command[index + 1]

                # Ignore non-volume filters.
                if not expression.startswith("volume="):
                    # Continue to the next filter.
                    continue

                # Read the required volume name.
                name: str = expression.removeprefix("volume=")

                # Require a matching volume mount.
                if not any(mount.get("Type") == "volume" and mount.get("Name") == name for mount in payload.get("Mounts") or []):
                    # Report no match.
                    return False

        # Report a match.
        return True

    # Build the network attachment mapping for one network name.
    def _network_attachments(self, name: str) -> dict[str, dict[str, str]]:
        # Prepare the attachments.
        attachments: dict[str, dict[str, str]] = {}

        # For each container.
        for identifier, payload in self.containers.items():
            # Read the attached networks.
            networks: Mapping[str, Any] = payload.get("NetworkSettings", {}).get("Networks") or {}

            # If the container uses the network, record its attachment.
            if name in networks:
                # Record the attachment.
                attachments[identifier] = {"Name": payload.get("Name", "").removeprefix("/"), "EndpointID": f"endpoint-{identifier}"}

        # Return the attachments.
        return attachments

    # Read one JSON-quoted override scalar.
    def _unquote(self, value: str) -> str:
        # Match a double-quoted scalar.
        match = _QUOTED.match(value)
        if match is not None:
            # Decode the JSON string body.
            return json.loads(f'"{match.group(1)}"')

        # Return the unquoted value.
        return value


# Define the public API of the scripted runtime engine.
__all__: list[str] = ["ParsedOverride", "RecordedCommand", "ScriptedComposeEngine"]
