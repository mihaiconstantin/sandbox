"""Verify catalogue-scoped secret bindings through the SDK without reading contents."""

# Imports.
from pathlib import Path

import pytest

# Import typed errors.
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.secrets import SecretFileError

# Import the test fixtures.
from sdk_fixtures import make_client, write_catalogue


# Prepare one temporary configuration home with a registered catalogue.
def prepare_home(tmp_path: Path) -> Path:
    # Create the home and registered catalogue.
    home: Path = tmp_path / "home"
    home.mkdir()
    write_catalogue(home)
    return home


# Create one readable host secret file.
def make_secret_file(tmp_path: Path) -> Path:
    # Write the secret file outside the configuration home.
    path: Path = tmp_path / "keys" / "example-secret"
    path.parent.mkdir()
    path.write_text("never displayed\n", encoding = "utf-8")
    return path


# Verify bind, get, list, and remove round-trip host paths and aliases only.
def test_secret_bindings_round_trip(tmp_path: Path) -> None:
    # Prepare a home, client, and secret file.
    home: Path = prepare_home(tmp_path)
    secret_file: Path = make_secret_file(tmp_path)
    client = make_client(home)

    # Bind the secret.
    binding = client.secrets.bind("default", "example-secret", secret_file)
    assert binding.catalogue == "default"
    assert binding.alias == "example-secret"
    assert binding.host_path == secret_file

    # Require the binding and listing.
    assert client.secrets.get("default", "example-secret") == binding
    assert client.secrets.list() == (binding,)
    assert client.secrets.get("default", "missing") is None

    # Remove the binding and require absence.
    assert client.secrets.remove("default", "example-secret") is True
    assert client.secrets.get("default", "example-secret") is None
    assert client.secrets.list() == ()
    assert client.secrets.remove("default", "example-secret") is False


# Verify invalid identifiers are rejected before reading or writing configuration.
def test_invalid_secret_identifiers_are_rejected(tmp_path: Path) -> None:
    # Prepare a client and secret file.
    home: Path = prepare_home(tmp_path)
    secret_file: Path = make_secret_file(tmp_path)
    client = make_client(home)

    # Require the typed input error for every identifier-taking operation.
    with pytest.raises(ConfigurationError):
        client.secrets.get("Default", "example-secret")
    with pytest.raises(ConfigurationError):
        client.secrets.bind("default", "Example-Secret", secret_file)
    with pytest.raises(ConfigurationError):
        client.secrets.remove("default", "Example-Secret")

    # Require no binding to be created.
    assert client.secrets.list() == ()


# Verify binding and removal require a resolvable catalogue registration.
def test_secret_operations_require_a_registration(tmp_path: Path) -> None:
    # Prepare an empty home and a readable secret file.
    home: Path = tmp_path / "home"
    home.mkdir()
    secret_file: Path = make_secret_file(tmp_path)
    client = make_client(home)

    # Require a registry error before saving or removing.
    with pytest.raises(RegistryError):
        client.secrets.bind("default", "example-secret", secret_file)
    with pytest.raises(RegistryError):
        client.secrets.remove("default", "example-secret")

    # Require listing to stay empty and readable without a registry.
    assert client.secrets.list() == ()
    assert client.secrets.get("default", "example-secret") is None


# Verify an unusable host file is rejected with its typed error.
def test_bind_rejects_an_unusable_secret_file(tmp_path: Path) -> None:
    # Prepare a home and a directory used as the secret path.
    home: Path = prepare_home(tmp_path)
    directory: Path = tmp_path / "not-a-file"
    directory.mkdir()
    client = make_client(home)

    # Require the secret-file error.
    with pytest.raises(SecretFileError) as raised:
        client.secrets.bind("default", "example-secret", directory)

    # Require the structured path.
    assert raised.value.path == directory
