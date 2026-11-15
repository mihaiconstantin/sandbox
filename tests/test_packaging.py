"""Verify the installed package metadata, scripts, typing marker, and wheel inputs."""

# Imports.
from __future__ import annotations

import re
import tomllib
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Any

# Locate the repository root from the test file.
ROOT: Path = Path(__file__).resolve().parents[1]

# Declare the exact runtime dependency set.
EXPECTED_DEPENDENCIES: dict[str, str] = {
    "click": ">=8.5.0",
    "rich": ">=15.0.0",
    "tomlkit": ">=0.15.2",
}

# Declare the console scripts around the composition entry point.
EXPECTED_SCRIPTS: dict[str, str] = {
    "sandbox": "sandbox.composition.main:main",
    "sb": "sandbox.composition.main:main",
}


# Read the parsed project metadata.
def project_metadata() -> dict[str, Any]:
    # Parse the repository pyproject file.
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding = "utf-8"))


# Split one dependency declaration into its normalized name and specifier.
def parse_dependency(requirement: str) -> tuple[str, str]:
    # Match the project name and the remaining version specifier.
    match: re.Match[str] | None = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)\s*(.*)", requirement)
    assert match is not None, requirement
    return match.group(1).lower().replace("_", "-"), match.group(2).strip()


# Verify the Python floor and typing classifier.
def test_python_and_typing_metadata() -> None:
    # Read the project table and classifiers.
    project: dict[str, Any] = project_metadata()["project"]
    classifiers: list[str] = project["classifiers"]

    # Require Python 3.11 and typed-package metadata.
    assert project["requires-python"] == ">=3.11"
    assert "Programming Language :: Python :: 3.11" in classifiers
    assert "Typing :: Typed" in classifiers
    assert "Programming Language :: Python :: 3.10" not in classifiers


# Verify the runtime dependency set stays minimal and backend-free.
def test_runtime_dependencies_are_exact_and_backend_free() -> None:
    # Read and normalize the declared dependencies.
    project: dict[str, Any] = project_metadata()["project"]
    dependencies: dict[str, str] = dict(parse_dependency(requirement) for requirement in project["dependencies"])

    # Require the approved libraries only, without optional extras.
    assert dependencies == EXPECTED_DEPENDENCIES
    assert "optional-dependencies" not in project
    assert "rich-click" not in dependencies
    assert "docker" not in dependencies


# Verify both console scripts resolve through the composition entry point.
def test_console_scripts_target_the_composition_entry_point() -> None:
    # Require the declared scripts.
    assert project_metadata()["project"]["scripts"] == EXPECTED_SCRIPTS

    # Require the installed scripts to match.
    installed: dict[str, str] = {
        entry_point.name: entry_point.value
        for entry_point in entry_points(group = "console_scripts")
        if entry_point.name in EXPECTED_SCRIPTS
    }
    assert installed == EXPECTED_SCRIPTS

    # Require the installed entry points to load the production callable.
    from sandbox.composition.main import main as composition_main

    for entry_point in entry_points(group = "console_scripts"):
        # Skip unrelated scripts.
        if entry_point.name not in EXPECTED_SCRIPTS:
            continue

        # Compare the loaded callable.
        entry: EntryPoint = entry_point
        assert entry.load() is composition_main


# Verify the root facade exposes the documented public surface only.
def test_root_facade_exports_the_documented_surface() -> None:
    # Import the public root package.
    import sandbox

    # Declare representative required exports across every public category.
    required: set[str] = {
        "SandboxClient",
        "BoxOperations",
        "VolumeOperations",
        "CatalogueOperations",
        "SecretOperations",
        "CreateBoxRequest",
        "CreateBoxResult",
        "Builder",
        "Runtime",
        "RuntimePreparation",
        "OutputSink",
        "ProgressPhase",
        "OutputChannel",
        "SILENT",
        "SandboxPlan",
        "RecipeDefinition",
        "VolumeDeclaration",
        "SandboxError",
        "BoxNotFound",
        "ConfigurationError",
    }
    assert required <= set(sandbox.__all__)
    for name in required:
        assert hasattr(sandbox, name), name

    # Require retired architecture and adapter names to stay absent.
    for retired in ("Application", "ApplicationFactory", "ComposeProvider", "BuildPolicy", "RecipeResolver", "ResolvedRecipe"):
        assert not hasattr(sandbox, retired), retired


# Verify the typing marker ships in the wheel.
def test_wheel_inputs_include_typing_marker() -> None:
    # Require the typing marker in the package source.
    marker: Path = ROOT / "src" / "sandbox" / "py.typed"
    assert marker.is_file()

    # Read the wheel build inputs.
    wheel: dict[str, Any] = project_metadata()["tool"]["hatch"]["build"]["targets"]["wheel"]

    # Require the source layout and no catalogue asset inclusion.
    assert wheel["sources"] == ["src"]
    assert "force-include" not in wheel
