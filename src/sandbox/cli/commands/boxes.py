# Imports.
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import click

# Import the CLI helpers.
from sandbox.cli.completion import complete_projects
from sandbox.cli.context import client_for, cli_context, default_home
from sandbox.cli.parameters import catalogue_argument, home_option, project_argument

# Import the public box values.
from sandbox.domain import RemovalPlan, RuntimeRef, secret_target

# Import the typed missing-secret failures.
from sandbox.errors.secrets import MissingSecret, SecretError

# Import the public SDK request.
from sandbox.sdk import CreateBoxRequest, CreateBoxResult, SandboxClient


# Check whether the command has an interactive terminal.
def is_interactive() -> bool:
    # Return whether standard input is a terminal.
    return sys.stdin.isatty()


# Prompt for a readable secret file.
def prompt_secret_file() -> Path:
    # Repeat until a valid file is provided.
    while True:
        # Ask for the secret file path.
        value: str = click.prompt("Path to secret file", type = str)

        # Expand the user directory.
        path: Path = Path(value).expanduser()

        # If the file is not readable.
        if not path.is_file() or not os.access(path, os.R_OK):
            # User feedback.
            click.secho(f"Secret file `{path}` does not exist or is not readable.", fg = "red")

            # Ask again.
            continue

        # Return the resolved file path without reading its contents.
        return path.resolve()


# Compose the actionable command that binds a missing secret.
def secret_command_hint(error: MissingSecret, home: Path) -> str:
    # Resolve the selected home so the hint matches the binding location.
    selected_home: Path = home.expanduser().resolve()

    # Compose the command that binds the missing secret in its catalogue.
    command_hint: str = f"sb create secret {error.alias} --file <path> --catalogue {error.catalogue}"

    # If the selected home differs from the default home.
    if selected_home != default_home().expanduser().resolve():
        # Append the selected home so the binding is saved where this command reads it.
        command_hint += f" --home {selected_home}"

    # Return the complete hint.
    return command_hint


# Remove a generated workspace only when it is still empty.
def remove_empty_generated(workspace: Path) -> None:
    # Ignore a missing or non-empty workspace without masking the operation result.
    try:
        # Remove the directory only when it has no entries.
        if not any(workspace.iterdir()):
            # Remove the empty generated directory.
            workspace.rmdir()

    # Ignore cleanup filesystem failures.
    except OSError:
        # Leave the workspace for the user to inspect.
        return


# Create the box command registered under the `create` group.
@click.command(name = "box")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    help = "The name of the project to create a box for.",
)
@click.option(
    "-d", "--project-dir",
    type = click.Path(exists = True, file_okay = False, dir_okay = True, path_type = Path),
    default = None,
    show_default = "a new empty temporary directory",
    help = "The existing project directory to mount inside the box.",
)
@click.option(
    "-c", "--catalogue",
    type = str,
    required = True,
    callback = catalogue_argument,
    help = "The catalogue containing the development recipe.",
)
@click.option(
    "-r", "--recipe",
    type = str,
    help = "The development recipe to provision. Defaults to the default recipe of the selected catalogue.",
)
@home_option(exists = True)
@click.option(
    "--build",
    is_flag = True,
    default = False,
    help = "Build the image even when it already exists.",
)
@click.pass_context
def create_box(
    ctx: click.Context,
    project: str,
    project_dir: Path | None,
    catalogue: str,
    recipe: str | None,
    home: Path,
    build: bool,
) -> None:
    """Create and start a box for a project."""

    # Resolve the inert client for the selected home before any workspace mutation.
    client: SandboxClient = client_for(ctx, home)

    # Track whether this invocation owns the project directory.
    generated: bool = project_dir is None

    # Create the default workspace only after Click has validated every option.
    workspace: Path = Path(tempfile.mkdtemp(prefix = "sb-box-")) if project_dir is None else project_dir

    # Track whether creation reached the success result.
    succeeded: bool = False

    # Declare the effective recipe reported by the SDK.
    effective_recipe: str

    try:
        # Scope transient progress to the create operation.
        with cli_context(ctx).presentation.output:
            # Repeat until the box is created.
            while True:
                # Attempt to create the box.
                try:
                    # Create the box and retain the effective recipe.
                    result: CreateBoxResult = client.boxes.create(
                        CreateBoxRequest(
                            project = project,
                            project_dir = workspace,
                            catalogue = catalogue,
                            recipe = recipe,
                            rebuild = build,
                        )
                    )

                # If a required secret is missing.
                except MissingSecret as error:
                    # If the command is not interactive.
                    if not is_interactive():
                        # Throw the actionable non-interactive hint through the presenter.
                        raise SecretError(
                            f"Secret `{error.alias}` is not configured. "
                            f"Recipe `{error.recipe}` requires it. "
                            f"Run `{secret_command_hint(error, home)}`."
                        ) from None

                    # Name the catalogue that requires the secret.
                    catalogue_scope: str = f" in catalogue `{error.catalogue}`"

                    # User feedback.
                    click.secho(
                        f"Secret `{error.alias}`{catalogue_scope} is required by recipe `{error.recipe}`.",
                        fg = "yellow",
                        italic = True,
                        color = ctx.color,
                    )

                    # Explain where the secret will be mounted.
                    click.secho(
                        f"It will be mounted read-only at `{secret_target(error.alias)}`.",
                        fg = "yellow",
                        italic = True,
                        color = ctx.color,
                    )

                    # Ask for the secret file.
                    secret_file: Path = prompt_secret_file()

                    # Save the binding through the SDK without reading the contents.
                    client.secrets.bind(error.catalogue, error.alias, secret_file)

                    # User feedback.
                    click.secho(f"Saved secret `{error.alias}` in catalogue `{error.catalogue}`.", fg = "green", color = ctx.color)

                # Otherwise, stop retrying.
                else:
                    # Retain the effective recipe.
                    effective_recipe = result.recipe

                    # Mark the operation successful before retaining its workspace.
                    succeeded = True

                    # Stop once creation succeeds.
                    break

    finally:
        # Remove a generated workspace only after a failed operation and only when still empty.
        if generated and not succeeded:
            # Clean the empty generated directory.
            remove_empty_generated(workspace)

    # User feedback.
    click.secho(f"Successfully created a box with recipe `{effective_recipe}` for the project `{project}`.", fg = "green", bold = True, color = ctx.color)


# Remove a box and its owned runtime resources.
@click.command(name = "box")
@click.argument(
    "project",
    type = str,
    callback = project_argument,
    shell_complete = complete_projects,
    help = "The name of the project whose box to remove.",
)
@click.option(
    "-y", "--yes",
    is_flag = True,
    default = False,
    help = "Skip the removal confirmation prompt.",
)
@click.pass_context
def remove_box(ctx: click.Context, project: str, yes: bool) -> None:
    """Remove a box and its resources."""

    # Resolve the home-bound client once for this command.
    client: SandboxClient = client_for(ctx)

    # Preview the resources planned for removal without mutating them.
    plan: RemovalPlan = client.boxes.plan_removal(project)

    # Display the project being removed.
    click.secho(f"\nRemoving resources for project `{project}`...", fg = "yellow", italic = True, color = ctx.color)

    # Display the containers scheduled for removal.
    click.secho("\nContainers", bold = True, color = ctx.color)

    # Declare the container.
    container: RuntimeRef

    # For each container.
    for container in plan.containers:
        # Display the container name.
        click.echo(f"  {container.name}")

    # If no containers exist.
    if not plan.containers:
        # Display none.
        click.echo("  None")

    # Display the networks scheduled for removal.
    click.secho("\nNetworks", bold = True, color = ctx.color)

    # Declare the network.
