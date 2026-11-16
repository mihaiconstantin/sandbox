# Imports.
import re
from pathlib import PurePosixPath

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.fields import validate_string
from sandbox.validation.identifiers import validate_identifier


# Represent one recipe declaration from a catalogue manifest.
class Recipe:
    # Compose filename.
    compose: str

    # Compose service name.
    service: str

    # Optional parent recipe.
    extends: str | None

    # Volume aliases.
    volumes: list[str]

    # Secret aliases.
    secrets: list[str]

    # Root execution permission.
    allow_root: bool

    # Validate the compose filename.
    def _validate_compose(self: "Recipe", compose: str) -> None:
        # Require a nonblank `docker` compose filename.
        validate_string(compose, "compose")

        # If the `docker` compose filename is not portable.
        if "\\" in compose or ":" in compose or "\x00" in compose or compose.endswith("/"):
            # Throw.
            raise ConfigurationError("compose", "Must be a portable relative file path.")

        # Parse the relative compose path.
        compose_path: PurePosixPath = PurePosixPath(compose)

        # If the compose path is absolute or traverses parents.
        if compose_path.is_absolute() or not compose_path.parts or ".." in compose_path.parts:
            # Throw.
            raise ConfigurationError("compose", "Must be a catalogue-relative file path without parent traversal.")

    # Validate the Compose service name.
    def _validate_service(self: "Recipe", service: str) -> None:
        # Require a literal Compose service name.
        validate_string(service, "service")

        # If the service name is invalid.
        if re.fullmatch(r"[a-zA-Z0-9._-]+", service) is None:
            # Throw.
            raise ConfigurationError("service", "Must be a literal Compose service name containing only letters, digits, periods, hyphens, or underscores.")

    # Validate the optional parent recipe.
    def _validate_extends(self: "Recipe", extends: str | None) -> None:
        # If the recipe declares a parent.
        if extends is not None:
            # Validate the parent identifier.
            validate_identifier(extends, "extends")

    # Validate and copy one alias list.
    def _validate_aliases(self: "Recipe", aliases: list[str], field: str, label: str) -> list[str]:
        # Require the aliases as a list.
        if not isinstance(aliases, list):
            # Throw.
            raise ConfigurationError(field, f"Must be a list of {label} aliases.")

        # Copy the aliases before validation.
        values: list[str] = list(aliases)

        # Prepare the seen aliases.
        seen: set[str] = set()

        # For each alias.
        for index, name in enumerate(values):
            # Validate the alias identifier.
            validate_identifier(name, f"{field}[{index}]")

            # If the alias is duplicated.
            if name in seen:
                # Throw.
                raise ConfigurationError(f"{field}[{index}]", f"{label.capitalize()} alias `{name}` is declared more than once in this recipe.")

            # Record the alias.
            seen.add(name)

        # Return the validated aliases.
        return values

    # Validate and copy the volume aliases.
    def _validate_volumes(self: "Recipe", volumes: list[str]) -> list[str]:
        # Return the validated volume aliases.
        return self._validate_aliases(volumes, "volumes", "volume")

    # Validate and copy the secret aliases.
    def _validate_secrets(self: "Recipe", secrets: list[str]) -> list[str]:
        # Return the validated secret aliases.
        return self._validate_aliases(secrets, "secrets", "secret")

    # Validate the root execution permission.
    def _validate_allow_root(self: "Recipe", allow_root: bool) -> None:
        # Require an exact Boolean root permission.
        if type(allow_root) is not bool:
            # Throw.
            raise ConfigurationError("allow_root", "Must be a Boolean.")

    # Initialize the recipe.
    def __init__(self: "Recipe", compose: str, service: str, extends: str | None = None, volumes: list[str] | None = None, secrets: list[str] | None = None, allow_root: bool = False) -> None:
        # Validate the recipe fields.
        self._validate_compose(compose)
        self._validate_service(service)
        self._validate_extends(extends)
        self._validate_allow_root(allow_root)

        # Validate and retain the aliases.
        self.volumes = self._validate_volumes(volumes if volumes is not None else [])
        self.secrets = self._validate_secrets(secrets if secrets is not None else [])

        # Retain the validated declaration.
        self.compose = compose
        self.service = service
        self.extends = extends
        self.allow_root = allow_root
