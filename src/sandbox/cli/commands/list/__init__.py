# Import the `list` group for root registration.
from sandbox.cli.commands.list.group import list_resources

# Define the public API of the `sandbox.cli.commands.list` package.
__all__: list[str] = ["list_resources"]
