"""Verify catalogue discovery, installation, validation, recipes, and removal through the SDK."""

# Imports.
from pathlib import Path

import pytest

# Import typed errors.
from sandbox.errors.catalogues import CatalogueInstallError, RegistryError
from sandbox.errors.configuration import ConfigurationError

# Import the public SDK.
from sandbox.sdk import RecipeListing

# Import the test fixtures.
from catalogue_fixtures import write_catalogue_repository
from sdk_fixtures import bind_secret, make_client, write_catalogue


# Prepare one temporary configuration home with a registered catalogue.
def prepare_home(tmp_path: Path) -> tuple[Path, Path]:
    # Create the home and registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    directory: Path = write_catalogue(home)
    return home, directory


# Verify discovery, install state, location, validation, and recipe listings.
def test_catalogue_read_operations(tmp_path: Path) -> None:
    # Prepare a registered catalogue and an unregistered directory.
    home, directory = prepare_home(tmp_path)
    (home / "catalogues" / "present").mkdir()
    client = make_client(home)

    # Require the registration listing.
    registrations = client.catalogues.list()
    assert [registration.name for registration in registrations] == ["default"]
    assert registrations[0].path == directory

    # Require registered and present states.
    state = client.catalogues.inspect_installation("default")
    assert state.registered is True
    assert state.directory_present is True

    # Require absent and present-only states.
    missing = client.catalogues.inspect_installation("missing")
    assert missing.registered is False
    assert missing.directory_present is False
    present = client.catalogues.inspect_installation("present")
    assert present.registered is False
    assert present.directory_present is True

    # Require location and validation.
    assert client.catalogues.locate("default") == directory
    assert client.catalogues.validate("default") is None

    # Require the sorted recipe listing with the default marker.
    assert client.catalogues.list_recipes("default") == (RecipeListing(name = "base", is_default = True),)


# Verify install returns the installed path and publishes the registration.
def test_install_returns_the_installed_path(tmp_path: Path) -> None:
    # Prepare a local source catalogue.
    source_root: Path = tmp_path / "source"
    source_root.mkdir()
    source: Path = write_catalogue(source_root, "local", register = False)
    home: Path = tmp_path / "home"
    home.mkdir()
    client = make_client(home)

    # Install the local source.
    installed: Path = client.catalogues.install("local", str(source), force = True)

    # Require the canonical installed path, directory, and registration.
    assert installed == home / "catalogues" / "local"
    assert installed.is_dir()
    assert [registration.name for registration in client.catalogues.list()] == ["local"]
    assert client.catalogues.inspect_installation("local").registered is True


# Verify the SDK installs one explicitly selected catalogue from a repository.
def test_install_selects_a_catalogue_from_a_multi_catalogue_source(tmp_path: Path) -> None:
    # Prepare a multi-catalogue source with distinct markers.
    source: Path = write_catalogue_repository(tmp_path / "source", ("base", "latex"))
    (source / "base" / "base-marker.txt").write_text("base", encoding = "utf-8")
    (source / "latex" / "latex-marker.txt").write_text("latex", encoding = "utf-8")
    home: Path = tmp_path / "home"
    home.mkdir()
    client = make_client(home)

    # Install the selected catalogue under a custom name.
    installed: Path = client.catalogues.install("team", str(source), which = "base")

    # Require only the selected catalogue content and the registration.
    assert installed == home / "catalogues" / "team"
    assert (installed / "base-marker.txt").is_file()
    assert not (installed / "latex").exists()
    assert [registration.name for registration in client.catalogues.list()] == ["team"]


# Verify the SDK requires explicit selection for every child catalogue.
def test_install_requires_explicit_selection_for_child_catalogues(tmp_path: Path) -> None:
    # Require a sole child catalogue to reject installation without a selector.
    sole_source: Path = write_catalogue_repository(tmp_path / "sole", ("base",))
    sole_home: Path = tmp_path / "sole-home"
    sole_home.mkdir()
    sole_client = make_client(sole_home)
    with pytest.raises(CatalogueInstallError) as raised:
        sole_client.catalogues.install("team", str(sole_source))
    assert "`base`" in str(raised.value)
    assert "--which" in str(raised.value)
    assert not (sole_home / "catalogues.toml").exists()

    # Require a multi-catalogue source to list every available directory.
    source: Path = write_catalogue_repository(tmp_path / "multi", ("base", "latex"))
    home: Path = tmp_path / "multi-home"
    home.mkdir()
    client = make_client(home)
    with pytest.raises(CatalogueInstallError) as raised:
        client.catalogues.install("team", str(source))
    assert "Available catalogues are `base` and `latex`" in str(raised.value)
    assert not (home / "catalogues.toml").exists()


# Verify the SDK rejects invalid selector types and values before publishing.
def test_install_validates_the_catalogue_selector(tmp_path: Path) -> None:
    # Prepare a multi-catalogue source and an absent home.
    source: Path = write_catalogue_repository(tmp_path / "source", ("base", "latex"))
    home: Path = tmp_path / "home"
    home.mkdir()
    client = make_client(home)

    # Require Python to reject a non-string selector.
    with pytest.raises(TypeError):
        client.catalogues.install("team", str(source), which = 1)  # pyright: ignore[reportArgumentType]

    # Require invalid selector values to use the typed catalogue error.
    with pytest.raises(CatalogueInstallError):
        client.catalogues.install("team", str(source), which = " ")

    # Require no configuration or registration to be created.
    assert not (home / "catalogues.toml").exists()
    assert client.catalogues.list() == ()


# Verify the SDK requires an explicit source for every installation.
def test_install_requires_a_source(tmp_path: Path) -> None:
    # Prepare a client with no configuration.
    home: Path = tmp_path / "home"
    home.mkdir()
    client = make_client(home)

    # Require Python to reject a missing source before any installation.
    with pytest.raises(TypeError):
        # Omit the source intentionally to exercise the required parameter.
        client.catalogues.install("local")  # pyright: ignore[reportCallIssue]

    # Require no configuration file to be created by the rejected call.
    assert not (home / "catalogues.toml").exists()


# Verify plan removal carries bindings and removes files, registration, and bindings.
def test_plan_and_remove_a_catalogue(tmp_path: Path) -> None:
    # Prepare a registered catalogue with a bound secret.
    home, directory = prepare_home(tmp_path)
    secret_file: Path = bind_secret(home)
    client = make_client(home)

    # Require the validated plan with the catalogue-scoped binding.
    plan = client.catalogues.plan_removal("default")
    assert plan is not None
    assert plan.registration.name == "default"
    assert plan.registration.path == directory
    assert plan.registration.bindings[0].alias == "example-secret"
    assert plan.registration.bindings[0].path == secret_file

    # Remove the catalogue through its plan.
    assert client.catalogues.remove(plan) is True
    assert not directory.exists()
    assert client.catalogues.list() == ()
    assert client.secrets.list() == ()
    assert client.catalogues.plan_removal("default") is None


# Verify removal by name reports whether anything was removed and rejects stale plans.
def test_remove_by_name_and_stale_plan_revalidation(tmp_path: Path) -> None:
    # Prepare a registered catalogue and a validated plan.
    home, directory = prepare_home(tmp_path)
    client = make_client(home)
    plan = client.catalogues.plan_removal("default")
    assert plan is not None

    # Remove by name, then require a second removal to report no change.
    assert client.catalogues.remove("default") is True
    assert not directory.exists()
    assert client.catalogues.remove("default") is False

    # Require the stale plan to fail revalidation instead of mutating anything.
    with pytest.raises(RegistryError):
        client.catalogues.remove(plan)


# Verify invalid catalogue identifiers are rejected before any mutation.
def test_invalid_catalogue_identifiers_are_rejected(tmp_path: Path) -> None:
    # Prepare a client with no configuration.
    home: Path = tmp_path / "home"
    home.mkdir()
    client = make_client(home)

    # Require the typed input error on every name-taking operation.
    operations = (
        client.catalogues.inspect_installation,
        client.catalogues.locate,
        client.catalogues.validate,
        client.catalogues.list_recipes,
        client.catalogues.plan_removal,
        client.catalogues.remove,
    )
    for operation in operations:
        with pytest.raises(ConfigurationError):
            operation("Default")

    # Require the same rule for installation.
    with pytest.raises(ConfigurationError):
        client.catalogues.install("Default", str(tmp_path / "source"))

    # Require no configuration file to be created by rejected input.
    assert not (home / "catalogues.toml").exists()


# Verify unknown catalogue and recipe names raise typed errors.
def test_unknown_catalogue_and_recipe_raise_typed_errors(tmp_path: Path) -> None:
    # Prepare a registered catalogue.
    home, _ = prepare_home(tmp_path)
    client = make_client(home)

    # Require the missing registration error.
    with pytest.raises(RegistryError):
        client.catalogues.locate("missing")

    # Require the recipe listing for the known catalogue.
    assert [listing.name for listing in client.catalogues.list_recipes("default")] == ["base"]
