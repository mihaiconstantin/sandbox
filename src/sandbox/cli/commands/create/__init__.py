# Imports.
from __future__ import annotations

from typing import ClassVar

import click


# Resolve aliases without listing them as separate commands.
class AliasGroup(click.Group):
    # Map each compatibility alias to its canonical command name.
    aliases: ClassVar[dict[str, str]] = {"catalog": "catalogue"}

    # Resolve an alias to its canonical command.
    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        # Resolve the alias, if present.
        canonical: str = self.aliases.get(cmd_name, cmd_name)

        # Return the canonical command.
        return super().get_command(ctx, canonical)


# Create the resource command group.
@click.group(name = "create", cls = AliasGroup)
def create_group() -> None:
    """Create a `sandbox` resource."""
