# Imports.
from pathlib import Path

# Import domain values.
from sandbox.domain.volume import VolumeDeclaration


# Represent one fully resolved catalogue recipe.
class ResolvedCatalogueRecipe:
    # Selected recipe name.
    name: str

    # Selected service.
    service: str

    # Parent-first recipe chain.
    recipes: list[str]

    # Parent-first compose paths.
    compose: list[Path]

    # Resolved physical volumes.
    volumes: list[VolumeDeclaration]

    # Selected root permission.
    allow_root: bool

    # Resolved secret aliases.
    secrets: list[str]

    # Validate the selected recipe identity.
    def _validate_name(self: "ResolvedCatalogueRecipe", name: str) -> None:
        # Require a nonblank name.
        if not isinstance(name, str) or not name:
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.name must be a nonblank string.")

    # Validate the selected service.
    def _validate_service(self: "ResolvedCatalogueRecipe", service: str) -> None:
        # Require a nonblank service.
        if not isinstance(service, str) or not service:
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.service must be a nonblank string.")

    # Validate and copy the recipe chain.
    def _validate_recipes(self: "ResolvedCatalogueRecipe", recipes: list[str]) -> list[str]:
        # Require a nonempty recipe chain.
        if not isinstance(recipes, list) or not recipes or not all(isinstance(item, str) and item for item in recipes):
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.recipes must be a nonempty list of recipe names.")

        # Return the copied chain.
        return list(recipes)

    # Validate and copy the compose paths.
    def _validate_compose(self: "ResolvedCatalogueRecipe", compose: list[Path]) -> list[Path]:
        # Require a nonempty path list.
        if not isinstance(compose, list) or not compose or not all(isinstance(path, Path) for path in compose):
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.compose must be a nonempty list of paths.")

        # Return the copied paths.
        return list(compose)

    # Validate and copy the resolved volumes.
    def _validate_volumes(self: "ResolvedCatalogueRecipe", volumes: list[VolumeDeclaration]) -> list[VolumeDeclaration]:
        # Require a volume list.
        if not isinstance(volumes, list) or not all(isinstance(volume, VolumeDeclaration) for volume in volumes):
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.volumes must be a list of VolumeDeclaration values.")

        # Return the copied volumes.
        return list(volumes)

    # Validate the root permission.
    def _validate_allow_root(self: "ResolvedCatalogueRecipe", allow_root: bool) -> None:
        # Require an exact Boolean.
        if type(allow_root) is not bool:
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.allow_root must be a Boolean.")

    # Validate and copy the secret aliases.
    def _validate_secrets(self: "ResolvedCatalogueRecipe", secrets: list[str]) -> list[str]:
        # Require a secret list.
        if not isinstance(secrets, list) or not all(isinstance(secret, str) and secret for secret in secrets):
            # Throw.
            raise ValueError("ResolvedCatalogueRecipe.secrets must be a list of secret aliases.")

        # Return the copied secrets.
        return list(secrets)

    # Initialize the resolved recipe.
    def __init__(self: "ResolvedCatalogueRecipe", name: str, service: str, recipes: list[str], compose: list[Path], volumes: list[VolumeDeclaration], allow_root: bool, secrets: list[str] | None = None) -> None:
        # Validate the selected recipe.
        self._validate_name(name)
        self._validate_service(service)
        self._validate_allow_root(allow_root)

        # Validate and retain the resolved fields.
        self.recipes = self._validate_recipes(recipes)
        self.compose = self._validate_compose(compose)
        self.volumes = self._validate_volumes(volumes)
        self.secrets = self._validate_secrets(secrets if secrets is not None else [])

        # Retain the selected identity.
        self.name = name
        self.service = service
        self.allow_root = allow_root
