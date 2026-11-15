# Installing <span class="font-sandbox font-bold from-sandbox-500 dark:from-sandbox-400 bg-linear-to-r from-[15px] to-(--vp-c-text-1) to-[35px] bg-clip-text text-transparent">sandbox</span>

On this page you can find instructions on how to get started with `sandbox`, or
`sb` in short.

## Requirements

To use `sb` you need the following:

- [Python](https://www.python.org/) `3.11` or newer
- [Docker Engine](https://docs.docker.com/engine/install/) with
  [Compose](https://docs.docker.com/compose/) `5.6.0` or newer and
  [Buildx](https://docs.docker.com/reference/cli/docker/buildx/) `0.17.0` or
  newer
- [`uv`](https://docs.astral.sh/uv/) for easy installation and upgrade

Before running commands, `sb` checks and reports a missing or unsupported tool
with the required version. It, however, never installs other tools on your host.

::: warning Security Boundary
`sb` provides convenience for local development. It is not intended as a
security boundary to contain unsupervised rouge AI agents or other untrusted
workloads. See [NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell) for a
production-oriented solution in that direction.
:::

## Install

You can install `sb` using `uv` from the GitHub repository using:

```bash
# Install the tool from the repository.
uv tool install git+https://github.com/mihaiconstantin/sandbox.git
```

At the point, `sb` is available in your path. You can verify the installation by
printing the installed version:

```bash
# Print the installed version.
sb --version
```

You can upgrade an existing installation by running:

```bash
# Upgrade the installed tool.
uv tool upgrade sandbox
```

To get started you can check out the CLI guide as show below, or keep reading
the documentation.

```bash
# Print the getting started guide.
sb guide
```
