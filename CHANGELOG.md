# Changelog

## sandbox 0.0.1

### Added
- Add the package metadata, locked runtime and development dependencies,
  console entry points, `hatch` build configuration, and `MIT` license.
- Add the typed public error family rooted at `SandboxError`, including
  structured `CommandFailure` facts, stable public types, and the `InputError`
  and `IncompleteRemoval` compatibility bases.
- Add immutable neutral domain values for box observations and box states,
  catalogues, recipes, volumes, secrets, mounts, plans, artifacts, and guest
  paths.
- Add the `Builder`, `Runtime`, and `OutputSink` protocols, the neutral policy
  validators, and the shipped fake adapters and output recorder used for
  daemon-free tests.
- Add the configuration store and catalogue implementation with manifest and
  recipe validation, parent resolution, registration, secret bindings, and
  installation from bundled, local, and `git` sources. Sources are staged and
  validated before registration, leaving the original source untouched.
- Add the `Docker` command runner and builder with `Compose` configuration
  resolution, image existence checks, local builds, image pulls, image reuse,
  `Buildx` and `Compose` preflight, and `local-image` and `docker-archive`
  artifacts.
- Add the `Compose` runtime with box creation, inspection, lifecycle, and
  removal, as well as initialization, volumes, secret delivery, and ownership
  checks. Unsafe labels, mounts, privileges, secrets, and artifact mismatches
  fail before mutation.
- Add the public Python SDK with `SandboxClient` and the box, volume, catalogue,
  and secret operations. The SDK is adapter-agnostic, accepts frozen dataclass
  requests, returns frozen dataclass results, and uses `SILENT` output by
  default.
- Add the CLI foundation with the `sandbox` and `sb` entry points, the `Click`
  command tree, `Rich` progress, typed error rendering, shell completion, and
  the read and lifecycle commands. Results and prompts go to stdout; progress,
  child output, errors, and diagnostics go to stderr.
- Add the SDK-backed catalogue and secret commands for creating, editing,
  listing, and removing catalogues, listing recipes, and binding, listing, and
  removing secrets.
- Add the SDK-backed volume commands for creating, listing, and removing
  managed volumes.
- Add the SDK-backed box creation and removal commands and the `guide` command,
  including default recipe selection, secret prompting, temporary project
  directories, and confirmation handling.
- Add the production composition root and adapter selection, the `py.typed`
  marker, and the checks that enforce the layering and packaging boundaries.
  The composition package is the only place that imports both the SDK and the
  `Docker` integrations.
- Add the installation guide, the `VitePress` site, the `GitHub Pages`
  deployment workflow, and the changelog. The documentation site deploys on
  pushes to `main`.
