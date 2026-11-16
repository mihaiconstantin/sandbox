# Overview

<Sandbox /> is a command-line tool and Python SDK for managing isolated local
development environments, which I call _boxes_. In a nutshell, a box belongs to
one project directory. The project stays on the host. The tools and state needed
to work on it live inside the box.

> [!Note]
>
> `sb` is the shorthand for the longer `sandbox` command. All examples in this
> guide use `sb` shorthand unless otherwise noted.

If you would rather skip the conceptual overview, jump to the
[Installation](/guide/installation) page to get started and follow the rest of
the guide from there.

## The Rationale for <Sandbox/>

Development tools spread across a machine. One project needs a particular
version of [`python`](https://www.python.org/). Another needs
[`R`](https://www.r-project.org/). A third needs the full [`TeX
Live`](https://www.tug.org/texlive/) distribution. An agent needs a writable
home and a few credentials. Installing everything on the host works just fine,
but there are cases when executing things in an isolated boxes brings some peace
of mind.

In other words, boxes reduce (i.e., not eliminate) potential system-wide damage.
They restrict the execution environment to what is needed for the project. `sb`
exists for developers who want this isolation, but without all the bells and
whistles of more complex solutions like [Docker
Sandboxes](https://docs.docker.com/ai/sandboxes/) or [Nvidia
OpenShell](https://build.nvidia.com/openshell).

## Core Pieces

A <u>**box**</u> is the unit of work. It represents a Docker environment with
its own filesystem and processes. It is tied to a host project directory and a
recipe. See [Boxes](/guide/boxes) for details.

A <u>**catalogue**</u> packages recipes for distribution. It is a self-contained
directory with a `catalogue.toml` manifest and a set of recipes. A catalogue
repository can hold one catalogue at its root or several catalogues in child
directories. See [Catalogues](/guide/catalogues) for details.

A <u>**recipe**</u> defines one environment. It contains a `Dockerfile`, a
`compose.yaml`, and an entry in the catalogue manifest `catalogue.toml`. A
recipe can extend one parent recipe. In such cases, the child inherits the
Docker configuration and requirements of the parent (e.g., base image, volumes,
secrets).

A <u>**volume**</u> is a persistent storage that can be used to store data that
needs to survive a box removal. A volume can be shared with other boxes. See
[Volumes](/guide/volumes) for details.

A <u>**secret**</u> is a host file that is bound to a box. It can be used to
provide sensitive data (e.g., credentials, keys) to the box without exposing it
in the project directory. Each box receives a read-only copy of the secret file
at `/run/secrets/<alias>`. See [Secrets](/guide/secrets) for details.

## Isolation

A box receives the host project directory, the volumes declared by its recipe,
and the secrets bound to its catalogue. It does not receive any other resources
from the host or the Docker socket.

While this setup keeps tools and agent state away from the host, it is not a
security boundary. The main limitation is that Docker containers (i.e., on which
a box is based) share the host kernel. A malicious recipe or a privileged mount
can weaken the isolation. For this reason, it is perhaps prudent to read the
recipes within a catalogue before running them.

> [!Note]
>
> I am working on adding support for a `microVM` runtime (i.e., like Docker
> Sandboxes is doing) via
> [`microsandbox`](https://github.com/microsandbox/microsandbox), which will
> provide a stronger isolation boundary since each box will run in its own
> kernel.

Next, the [Installation](/guide/installation) guide covers prerequisites,
installation, and upgrades.
