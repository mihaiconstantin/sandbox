# Import catalogue declarations.
from sandbox.catalogue.recipe import Recipe
from sandbox.domain.volume import VolumeDeclaration

# Import errors and validation.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation import fields, identifiers


# Represent one validated catalogue manifest.
class Catalogue:
    # Catalogue name.
    name: str

    # Catalogue version.
    version: str

    # Manifest schema version.
    schema_version: int

    # Recipe declarations.
    recipes: dict[str, Recipe]

    # Volume declarations.
    volumes: dict[str, VolumeDeclaration]

    # Optional default recipe.
    default_recipe: str | None

    # Validate the catalogue name.
    def _validate_name(self: "Catalogue", name: str) -> None:
        # Validate the catalogue identifier.
        identifiers.validate_identifier(name, "catalogue.name")

    # Validate the catalogue version.
    def _validate_version(self: "Catalogue", version: str) -> None:
        # Require a nonblank version string.
        fields.validate_string(version, "catalogue.version")

    # Validate the manifest schema version.
    def _validate_schema_version(self: "Catalogue", schema_version: int) -> None:
        # If the schema version is not an integer.
        if type(schema_version) is not int:
            # Throw.
            raise ConfigurationError("catalogue.schema_version", "Must be an integer.")

        # If the schema version is unsupported.
        if schema_version != 1:
            # Throw.
            raise ConfigurationError("catalogue.schema_version", f"Unsupported schema version `{schema_version}`; expected `1`.")

    # Validate and copy the recipe declarations.
    def _validate_recipes(self: "Catalogue", recipes: dict[str, Recipe]) -> dict[str, Recipe]:
        # Require a recipe table.
        fields.require_mapping(recipes, "recipes", message = "Must be a table of recipe declarations.")

        # Copy the recipe table before validation.
        values: dict[str, Recipe] = dict(recipes)

        # If no recipes are declared.
        if not values:
            # Throw.
            raise ConfigurationError("recipes", "Must declare at least one recipe.")

        # For each recipe identifier and declaration.
        for recipe_name, recipe in values.items():
            # Prepare the recipe field name.
            field_name: str = f"recipes.{recipe_name}" if isinstance(recipe_name, str) else "recipes"

            # Validate the recipe identifier.
            identifiers.validate_identifier(recipe_name, field_name)

            # If the recipe declaration is invalid.
            if not isinstance(recipe, Recipe):
                # Throw.
                raise ConfigurationError(field_name, "Must be a Recipe declaration.")

        # Return the validated recipe table.
        return values

    # Validate and copy the volume declarations.
    def _validate_volumes(self: "Catalogue", volumes: dict[str, VolumeDeclaration] | None) -> dict[str, VolumeDeclaration]:
        # Require a volume table, defaulting to an empty one.
        volumes = {} if volumes is None else volumes
        fields.require_mapping(volumes, "volumes", message = "Must be a table of volume declarations.")

        # Copy the volume table before validation.
        values: dict[str, VolumeDeclaration] = dict(volumes)

        # For each volume identifier and declaration.
        for volume_name, volume in values.items():
            # Prepare the volume field name.
            field_name: str = f"volumes.{volume_name}" if isinstance(volume_name, str) else "volumes"

            # Validate the volume identifier.
            identifiers.validate_identifier(volume_name, field_name)

            # If the volume declaration is invalid.
            if not isinstance(volume, VolumeDeclaration):
                # Throw.
                raise ConfigurationError(field_name, "Must be a Volume declaration.")

        # Return the validated volume table.
        return values

    # Validate the optional default recipe.
    def _validate_default_recipe(self: "Catalogue", default_recipe: str | None, recipes: dict[str, Recipe]) -> None:
        # If no default recipe is declared.
        if default_recipe is None:
            # Return.
            return

        # Require a nonblank recipe name.
        fields.validate_string(default_recipe, "catalogue.default_recipe")

        # Require the default recipe to be declared.
        if default_recipe not in recipes:
            # Throw.
            raise ConfigurationError("catalogue.default_recipe", f"Recipe `{default_recipe}` is not declared in the catalogue.")

    # Initialize the catalogue.
    def __init__(
        self: "Catalogue",
        name: str,
        version: str,
        schema_version: int,
        recipes: dict[str, Recipe],
        volumes: dict[str, VolumeDeclaration] | None = None,
        default_recipe: str | None = None,
    ) -> None:
        # Validate the catalogue metadata.
        self._validate_name(name)
        self._validate_version(version)
        self._validate_schema_version(schema_version)

        # Validate and retain the declarations.
        self.recipes = self._validate_recipes(recipes)
        self.volumes = self._validate_volumes(volumes)

        # Validate and retain the optional default recipe.
        self._validate_default_recipe(default_recipe, self.recipes)
        self.default_recipe = default_recipe

        # Retain the validated metadata.
        self.name = name
        self.version = version
        self.schema_version = schema_version
