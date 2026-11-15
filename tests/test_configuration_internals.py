# Imports.
from pathlib import Path
from unittest import mock

import pytest

# Import catalogue and configuration seams.
from sandbox.catalogue.manifest import load_catalogue
from sandbox.configuration.registry import load_registry
from sandbox.configuration.store import ConfigurationStore

# Import typed configuration errors.
from sandbox.errors import SandboxError
from sandbox.errors.catalogues import RegistryError
from sandbox.errors.configuration import ConfigurationError
from sandbox.errors.secrets import SecretFileError


# Write a registry document into a temporary home.
def write_registry(home: Path, document: str) -> Path:
    # Create the home and write the registry as UTF-8.
    home.mkdir(parents = True, exist_ok = True)
    registry_file: Path = home / "catalogues.toml"
    registry_file.write_text(document, encoding = "utf-8")

    # Return the registry path.
    return registry_file


# Create an existing canonical catalogue directory.
def make_catalogue_directory(home: Path, name: str = "default") -> Path:
    # Create the canonical catalogue directory.
    directory: Path = home / "catalogues" / name
    directory.mkdir(parents = True, exist_ok = True)

    # Return the catalogue directory.
    return directory


# Verify store construction does not touch the filesystem or resolve the home.
def test_store_construction_defers_home_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Track home-expanding calls without changing their behavior.
    calls: list[tuple[str, Path]] = []
    original_expanduser = Path.expanduser
    original_resolve = Path.resolve

    def track_expanduser(path: Path) -> Path:
        calls.append(("expanduser", Path(path)))
        return original_expanduser(path)

    def track_resolve(path: Path, strict: bool = False) -> Path:
        calls.append(("resolve", Path(path)))
        return original_resolve(path, strict = strict)

    monkeypatch.setattr(Path, "expanduser", track_expanduser)
    monkeypatch.setattr(Path, "resolve", track_resolve)

    # Construct the store without requiring the home to exist.
    home: Path = tmp_path / "missing-sandbox"
    store: ConfigurationStore = ConfigurationStore(home)
    assert calls == []

    # Require the home to resolve only when a caller asks for it.
    assert store.home == home
    assert ("resolve", home) in calls
    assert store.registry_file == home / "catalogues.toml"
    assert store.destination("default") == home / "catalogues" / "default"


# Verify the documentation-defined registration keys are enforced on every read path.
@pytest.mark.parametrize(
    "document",
    [
        '[catalogues.default]\ntype = "local"\npath = "catalogues/default"\nextra = "x"\n',
        '[catalogues.default]\ntype = "local"\npath = "catalogues/default"\nversion = "1"\n',
    ],
)
def test_registration_reads_reject_extra_fields(tmp_path: Path, document: str) -> None:
    # Prepare a valid canonical directory so only the schema can fail.
    home: Path = tmp_path / "sandbox"
    registry_file: Path = write_registry(home, document)
    make_catalogue_directory(home)
    store: ConfigurationStore = ConfigurationStore(home)

    # Read the registration through every store read path.
    readers = (
        store.registrations,
        lambda: store.registration("default"),
        lambda: store.resolve("default"),
        lambda: store.catalogue_directory("default"),
    )
    for reader in readers:
        with pytest.raises(RegistryError) as raised:
            reader()
        assert str(registry_file) in str(raised.value)
        assert "extra" in str(raised.value) or "version" in str(raised.value)


# Verify registrations must use the canonical managed catalogue path.
@pytest.mark.parametrize(
    "registered_path",
    [
        "catalogues/other",
        "../outside/default",
        "/tmp/elsewhere/default",
        "./catalogues/elsewhere/default",
    ],
)
def test_registration_reads_reject_noncanonical_paths(tmp_path: Path, registered_path: str) -> None:
    # Prepare a canonical directory so only the path can fail.
    home: Path = tmp_path / "sandbox"
    registry_file: Path = write_registry(
        home,
        f'[catalogues.default]\ntype = "local"\npath = "{registered_path}"\n',
    )
    make_catalogue_directory(home)
    store: ConfigurationStore = ConfigurationStore(home)

    # Read the registration through every store read path.
    readers = (
        store.registrations,
        lambda: store.registration("default"),
        lambda: store.resolve("default"),
    )
    for reader in readers:
        with pytest.raises(RegistryError) as raised:
            reader()
        assert str(registry_file) in str(raised.value)
        assert "canonical" in str(raised.value)


# Verify an absolute canonical path remains valid on read.
def test_registration_reads_accept_an_absolute_canonical_path(tmp_path: Path) -> None:
    # Prepare an absolute canonical registration.
    home: Path = tmp_path / "sandbox"
    directory: Path = make_catalogue_directory(home)
    write_registry(
        home,
        f'[catalogues.default]\ntype = "local"\npath = "{directory}"\n',
    )
    store: ConfigurationStore = ConfigurationStore(home)

    # Require the registration and resolved directory.
    registration = store.registration("default")
    assert registration is not None
    assert registration.path == directory
    assert store.resolve("default") == directory


# Verify a missing registry is a clean typed error on resolving paths.
def test_missing_registry_is_a_configuration_error(tmp_path: Path) -> None:
    # Prepare a home without a registry.
    home: Path = tmp_path / "sandbox"
    home.mkdir()
    store: ConfigurationStore = ConfigurationStore(home)
    registry_file: Path = home / "catalogues.toml"

    # Require clean typed failures instead of raw file errors.
    with pytest.raises(RegistryError) as raised:
        store.resolve("default")
    assert isinstance(raised.value, SandboxError)
    assert isinstance(raised.value, ValueError)
    assert str(registry_file) in str(raised.value)

    # Require the discovery hint to remain for the required lookup.
    with pytest.raises(RegistryError) as raised:
        store.require("default")
    assert "Run `sb list catalogues`" in str(raised.value)

    # Require listing and registration checks to preserve their empty results.
    assert store.registrations() == ()
    assert store.registration("default") is None

    # Require saving a binding to report the missing registry cleanly.
    secret_file: Path = tmp_path / "secret"
    secret_file.write_text("secret\n", encoding = "utf-8")
    with pytest.raises(RegistryError) as raised:
        store.save_secret("default", "token", secret_file)
    assert str(registry_file) in str(raised.value)


# Verify registry reads translate missing files, decoding failures, malformed TOML, and OS failures.
def test_registry_reads_are_typed_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Require a missing registry to include its path.
    missing: Path = tmp_path / "missing" / "catalogues.toml"
    with pytest.raises(RegistryError) as raised:
        load_registry(missing)
    assert str(missing) in str(raised.value)

    # Require a non-UTF-8 registry to be reported without a raw decode error.
    home: Path = tmp_path / "decoded"
    write_registry(home, "")
    registry_file: Path = home / "catalogues.toml"
    registry_file.write_bytes(b"\xff\xfe")
    with pytest.raises(RegistryError) as raised:
        load_registry(registry_file)
    assert str(registry_file) in str(raised.value)
    assert "UTF-8" in str(raised.value)

    # Require malformed TOML to include the registry path.
    write_registry(home, "[catalogues.default\n")
    with pytest.raises(RegistryError) as raised:
        load_registry(registry_file)
    assert str(registry_file) in str(raised.value)

    # Require an OS read failure to become a registry error.
    write_registry(home, "")
    with monkeypatch.context() as context:
        context.setattr(Path, "read_text", mock.Mock(side_effect = PermissionError("denied")))
        with pytest.raises(RegistryError) as raised:
            load_registry(registry_file)
    assert str(registry_file) in str(raised.value)


# Verify a missing or non-directory manifest is a typed configuration error.
def test_manifest_paths_are_configuration_errors(tmp_path: Path) -> None:
    # Require a missing catalogue directory to name the path.
    missing: Path = tmp_path / "missing"
    with pytest.raises(ConfigurationError) as raised:
        load_catalogue(missing)
    assert str(missing) in str(raised.value)

    # Require a catalogue path that is a file to name the path.
    directory: Path = tmp_path / "sandbox"
    directory.mkdir()
    regular_file: Path = directory / "file"
    regular_file.write_text("text\n", encoding = "utf-8")
    with pytest.raises(ConfigurationError) as raised:
        load_catalogue(regular_file)
    assert str(regular_file) in str(raised.value)

    # Require a missing manifest to name the manifest path.
    with pytest.raises(ConfigurationError) as raised:
        load_catalogue(directory)
    assert str(directory / "catalogue.toml") in str(raised.value)


# Verify a non-UTF-8 manifest is a typed configuration error with its path.
def test_non_utf8_manifest_is_a_configuration_error(tmp_path: Path) -> None:
    # Prepare a catalogue with a non-UTF-8 manifest.
    directory: Path = tmp_path / "sandbox"
    directory.mkdir()
    manifest: Path = directory / "catalogue.toml"
    manifest.write_bytes(b"\xff\xfe")

    # Require a clean encoding error that names the manifest.
    with pytest.raises(ConfigurationError) as raised:
        load_catalogue(directory)
    assert str(manifest) in str(raised.value)
    assert "UTF-8" in str(raised.value)


# Verify unusable secret files are typed errors with resolved path facts.
def test_secret_file_failures_are_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a registered catalogue with an unreadable host file.
    home: Path = tmp_path / "sandbox"
    write_registry(home, '[catalogues.default]\ntype = "local"\npath = "catalogues/default"\n')
    make_catalogue_directory(home)
    secret_file: Path = home / "keys" / "token"
    secret_file.parent.mkdir()
    secret_file.write_text("secret\n", encoding = "utf-8")
    store: ConfigurationStore = ConfigurationStore(home)

    # Save the binding under a simulated access denial.
    with monkeypatch.context() as context:
        context.setattr("sandbox.configuration.secrets.os.access", lambda *args: False)
        with pytest.raises(SecretFileError) as raised:
            store.save_secret("default", "token", secret_file)
    assert raised.value.path == secret_file.resolve()
    assert raised.value.reason

    # Require a missing host file to be typed when loading a binding.
    store.save_secret("default", "token", secret_file)
    secret_file.unlink()
    with pytest.raises(SecretFileError) as raised:
        store.load_secret("default", "token")
    assert raised.value.path == secret_file.resolve()


# Verify configuration-facing values are the neutral domain registry values.
def test_configuration_values_reuse_domain_registry_values() -> None:
    # Import the configuration modules and the neutral registry values.
    from sandbox.configuration import registry, secrets, store
    from sandbox.domain import registry as domain_registry

    # Require one value identity across every configuration import path.
    assert registry.CatalogueRegistration is domain_registry.CatalogueRegistration
    assert secrets.SecretBinding is domain_registry.SecretBinding
    assert store.CatalogueRegistration is domain_registry.CatalogueRegistration
    assert store.SecretBinding is domain_registry.SecretBinding
