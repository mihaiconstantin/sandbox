# Imports.
import inspect

import click

# Section headings that receive the guide styling.
GUIDE_HEADINGS = (
    "Details",
    "Getting Started",
    "Managing Catalogues",
    "Managing Boxes",
    "Managing Volumes",
    "Managing Secrets",
    "More Information"
)


# The `sandbox` guide text.
GUIDE_TEXT = inspect.cleandoc(f"""
    {click.style("`sandbox`", fg = "blue", bold = True)} or {click.style("`sb`", fg = "blue", bold = True)} is a tool for managing isolated development environments.

    Details

    {click.style("`sandbox`", fg = "blue", bold = True)} is designed around the following main concepts:

      \u2219 A {click.style("box", bold = True, italic = True)} is a `docker`-based development environment associated with a local project directory. Boxes provide isolated execution environments for development tools and agents while retaining access to explicitly mounted resources.

      \u2219 A {click.style("catalogue", bold = True, italic = True)} is a collection of reusable development recipes.

      \u2219 A {click.style("recipe", bold = True, italic = True)} defines the `docker` configuration needed to provision a particular type of environment, such as a base Ubuntu environment or an R environment.

      \u2219 A {click.style("volume", bold = True, italic = True)} is persistent `docker`-managed storage that can be shared between boxes and survives container removal.

      \u2219 A {click.style("secret", bold = True, italic = True)} is a user-owned file on the host that is mounted into a box. Secrets are declared by recipes and bound to host paths by the user.

    Getting Started

      {click.style("# Create a catalogue named `my-catalogue` from a local catalogue directory.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} catalogue my-catalogue --source ./catalogue

      {click.style("# Create a box for the project `my-project` in the directory `~/Repositories/my-project` using the default recipe of the catalogue.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} box my-project \\
          --project-dir ~/Repositories/my-project \\
          --catalogue my-catalogue

      {click.style("# Enter the box for the project `my-project`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("enter", bold = True, fg = "green")} my-project

    Managing Catalogues

      {click.style("# Create a catalogue named `team` from a `git` repository.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} catalogue team --source https://example.com/catalogue.git

      {click.style("# Create the `base` catalogue from a repository with one self-contained catalogue per directory.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} catalogue base -s ./catalogues --which base

      {click.style("# List all registered catalogues.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("list", bold = True, fg = "green")} catalogues

      {click.style("# Edit the registered catalogue `my-catalogue`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("edit", bold = True, fg = "green")} catalogue my-catalogue

      {click.style("# Remove the registered catalogue `my-catalogue`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("remove", bold = True, fg = "green")} catalogue my-catalogue

    Managing Boxes

      {click.style("# List all available boxes.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("list", bold = True, fg = "green")} boxes

      {click.style("# Show the status of the box for the project `my-project`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("status", bold = True, fg = "green")} my-project

      {click.style("# Start the box for the project `my-project`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("start", bold = True, fg = "green")} my-project

      {click.style("# Stop the box for the project `my-project`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("stop", bold = True, fg = "green")} my-project

      {click.style("# Remove the box for the project `my-project`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("remove", bold = True, fg = "green")} box my-project

    Managing Volumes

      {click.style("# Create a volume named `my-volume`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} volume my-volume

      {click.style("# List all available volumes.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("list", bold = True, fg = "green")} volumes

      {click.style("# Remove the volume named `my-volume`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("remove", bold = True, fg = "green")} volume my-volume

    Managing Secrets

      {click.style("# Set the secret `example-secret` to the file `~/.keys/example-secret`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("create", bold = True, fg = "green")} secret example-secret \\
          --file ~/.keys/example-secret \\
          --catalogue team

      {click.style("# List all available secrets.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("list", bold = True, fg = "green")} secrets

      {click.style("# Remove the secret `example-secret`.", fg = "bright_black", italic = True)}
      {click.style("sb", bold = True, fg = "blue")} {click.style("remove", bold = True, fg = "green")} secret example-secret --catalogue team

    More Information

    Run `{click.style("sb", bold = True, fg = "blue")} <{click.style("command", bold = True, fg = "green")}> --help` for command-specific {click.style("options", italic = True)} and usage.
    """
).strip()


# Command to print the `sandbox` guide.
@click.command(name = "guide")
def guide() -> None:
    """Print a guide for getting started with `sandbox`."""

    # Declare the guide line.
    line: str

    # Print each guide line.
    for line in GUIDE_TEXT.splitlines():
        # If the line is a section heading.
        if line in GUIDE_HEADINGS:
            click.echo(click.style(line, bold = True, underline = True))
        # Otherwise.
        else:
            click.echo(click.formatting.wrap_text(line, preserve_paragraphs = True))


# Define the public API of the `sandbox.cli.commands.guide` module.
__all__: list[str] = ["GUIDE_HEADINGS", "GUIDE_TEXT", "guide"]
