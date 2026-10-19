"""Verify the shared Click-free identifier and volume-name rules."""

# Imports.
import subprocess
import sys

import pytest

# Import the shared rules.
from sandbox.errors.configuration import ConfigurationError
from sandbox.validation.identifiers import validate_identifier, validate_volume_name


# Verify the shared identifier rule accepts the lowercase namespace.
@pytest.mark.parametrize("value", ["a", "default", "my-catalogue_2"])
def test_identifier_accepts_the_lowercase_namespace(value: str) -> None:
    # Accept the identifier.
    validate_identifier(value, "catalogue")


# Verify the shared identifier rule rejects malformed values.
@pytest.mark.parametrize("value", ["", "Default", "-leading", "a b", "a/b", None, 1])
def test_identifier_rejects_malformed_values(value: object) -> None:
    # Reject the identifier with its field.
    with pytest.raises(ConfigurationError) as raised:
        validate_identifier(value, "catalogue")
    assert raised.value.field == "catalogue"


# Verify the shared volume-name rule reports its dedicated field.
@pytest.mark.parametrize("value", ["", "a", ".hidden", "-hidden", "a b", "a/b", None, 1])
def test_volume_name_rejects_malformed_values(value: object) -> None:
    # Reject the volume name with the shared field.
    with pytest.raises(ConfigurationError) as raised:
        validate_volume_name(value)
    assert raised.value.field == "volume.name"


# Verify importing the shared module does not import Click.
def test_validation_import_is_click_free() -> None:
    # Block Click before importing the shared module.
    script = """
import importlib.abc
import sys

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "click" or fullname.startswith("click."):
            raise ImportError("blocked import: click")
        return None

sys.meta_path.insert(0, Blocker())
from sandbox.validation.identifiers import validate_identifier, validate_volume_name
validate_identifier("default", "catalogue")
validate_volume_name("shared")
assert "click" not in sys.modules
print("ok")
"""

    # Run the import in a fresh interpreter.
    completed = subprocess.run([sys.executable, "-c", script], capture_output = True, text = True)

    # Require a clean import and rule use.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
