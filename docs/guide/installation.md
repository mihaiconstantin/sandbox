# Installation

## Requirements

- [`python`](https://www.python.org/) version `3.11` or newer
- [Docker Engine](https://docs.docker.com/engine/) with [Docker Compose](https://docs.docker.com/compose/) or [Docker Desktop](https://docs.docker.com/desktop/) with Docker Compose
- [Docker Buildx](https://docs.docker.com/build/buildx/) version `0.17.0` or newer when `sb create box` must build a recipe image
- [`uv`](https://docs.astral.sh/uv/) version `0.13.6` or newer for the installation command below
- [`git`](https://git-scm.com/) only when installing a catalogue from a `git` URL

`sandbox` checks each host tool when a command needs it. It never installs Docker, Compose, Buildx, `git`, or another host tool. A missing or unsupported tool stops the command before the box configuration changes and reports the tool, the required version, and the command to run.

::: warning Not a security boundary
`sandbox` provides convenience for local development. It is not intended to contain unsupervised AI agents or other untrusted workloads. See [NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell) for a production-oriented solution.
:::

## Check the prerequisites

Run the following commands on the host:

```bash
# Check the Python version. It must be 3.11 or newer.
python --version

# Check that the Docker daemon is reachable.
docker info

# Check the Docker Compose version. It must be 5.6.0 or newer.
docker compose version

# Check the Docker Buildx version. It must be 0.17.0 or newer when an image is built.
docker buildx version
```

Docker Compose `5.6.0` is the supported floor. `sandbox` uses Compose profiles, `extends`, `additional_contexts: service:<name>`, and a generated initialization hook; a profile-disabled service used as an additional build context must load for the bundled recipes. The runner reports an unsupported Compose version before it resolves a recipe.

Docker Buildx `0.17.0` is required only when `sb create box` actually builds an image. Reusing a present local image and pulling a missing image-only service do not require Buildx.

`git` is required only for `sb create catalogue --source <git-url>`.

## Install the tool

The simplest way to install `sandbox` is using the `python` package manager `uv`:

```bash
# Install the tool from the repository.
uv tool install git+https://github.com/mihaiconstantin/sandbox.git
```

After running the command above, both `sandbox` and `sb` will be available in your path.

To upgrade an existing installation, run:

```bash
# Upgrade the installed tool.
uv tool upgrade sandbox
```

## Verify the installation

```bash
# Print the installed version.
sandbox --version

# Print the getting started guide.
sandbox guide
```

Both commands work without Docker, Compose, or Buildx because they construct no SDK client and probe no host tool.

## Diagnose prerequisite failures

`sandbox` writes prerequisite diagnostics to stderr and exits with status `1`. The message names the failed tool and the requirement. Do not install a host tool automatically from a script; install and configure it yourself, then rerun the command.

| Symptom | Check | Resolution |
|---|---|---|
| `docker` is not found | `docker --version` | Install Docker Engine or Docker Desktop and add `docker` to `PATH`. |
| The Docker daemon is not reachable | `docker info` | Start the daemon or Docker Desktop. A stopped daemon is reported as an engine failure with the engine status. |
| Docker Compose is missing | `docker compose version` | Install the Compose plugin and confirm that `docker compose` is available, not only `docker-compose`. |
| Docker Compose is too old | `docker compose version` | Upgrade Docker Compose to `5.6.0` or newer. |
| A build reports Buildx is missing or too old | `docker buildx version` | Install or upgrade Docker Buildx to `0.17.0` or newer. A recipe that reuses a present image can still create a box. |
| A `git` catalogue install fails | `git --version` | Install `git`, or use a local directory or the bundled catalogue. |

## Next steps

- Read the [project README](https://github.com/mihaiconstantin/sandbox#readme) for catalogues, boxes, volumes, secrets, and the Python SDK.
- Read the [architecture guide](../architecture.md) for the SDK operations, ports, Docker builder, Compose runtime, composition root, output policy, and verification tiers.
- Read the [decision records](https://github.com/mihaiconstantin/sandbox/tree/main/docs/adr) for the accepted architecture choices.
