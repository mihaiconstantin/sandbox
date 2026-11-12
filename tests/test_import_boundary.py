"""Verify the final package layering, import direction, and retired surface."""

# Imports.
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

# Locate the source tree from the test file.
SOURCE_ROOT: Path = Path(__file__).resolve().parents[1] / "src"
PACKAGE_ROOT: Path = SOURCE_ROOT / "sandbox"

# Declare the production packages and their permitted first-party import roots.
LAYER_RULES: dict[str, frozenset[str]] = {
    "errors": frozenset({"sandbox.errors"}),
    "domain": frozenset({"sandbox.domain"}),
    "ports": frozenset({"sandbox.domain", "sandbox.errors", "sandbox.ports"}),
    "policy": frozenset({"sandbox.domain", "sandbox.errors", "sandbox.policy", "sandbox.ports"}),
    "testing": frozenset({"sandbox.domain", "sandbox.errors", "sandbox.ports", "sandbox.testing"}),
    "validation": frozenset({"sandbox.errors", "sandbox.validation"}),
    "configuration": frozenset({"sandbox.configuration", "sandbox.domain", "sandbox.errors", "sandbox.validation"}),
    "catalogue": frozenset({"sandbox.catalogue", "sandbox.configuration", "sandbox.domain", "sandbox.errors", "sandbox.validation"}),
    "sdk": frozenset({"sandbox.catalogue", "sandbox.configuration", "sandbox.domain", "sandbox.errors", "sandbox.policy", "sandbox.ports", "sandbox.sdk", "sandbox.validation"}),
    "integrations": frozenset({"sandbox.domain", "sandbox.errors", "sandbox.integrations", "sandbox.ports", "sandbox.validation"}),
    "cli": frozenset({"sandbox.cli", "sandbox.domain", "sandbox.errors", "sandbox.ports", "sandbox.sdk", "sandbox.validation"}),
    "composition": frozenset({"sandbox.cli", "sandbox.composition", "sandbox.domain", "sandbox.errors", "sandbox.integrations", "sandbox.ports", "sandbox.sdk"}),
}

# Declare the packages that may use Click and Rich.
CLICK_PACKAGES: frozenset[str] = frozenset({"cli"})
RICH_PACKAGES: frozenset[str] = frozenset({"cli/presentation"})

# Declare every module removed by the final contract cleanup.
RETIRED_MODULES: tuple[str, ...] = (
    "sandbox.application",
    "sandbox.providers",
    "sandbox.paths",
    "sandbox.composition.legacy",
    "sandbox.domain.legacy",
    "sandbox.errors.legacy",
    "sandbox.ports.legacy",
    "sandbox.policy.recipe",
    "sandbox.testing.artifact",
    "sandbox.testing.engine",
    "sandbox.cli.cli",
    "sandbox.cli.application",
    "sandbox.cli.errors",
    "sandbox.cli.volume_errors",
    "sandbox.cli.formatting",
    "sandbox.cli.environment",
    "sandbox.cli.completion_sdk",
    "sandbox.cli.commands_sdk",
    "sandbox.configuration.values",
    "sandbox.catalogue.volume",
)

# Declare every retired symbol that must not survive in production code.
RETIRED_SYMBOLS: tuple[str, ...] = (
    "Application",
    "ApplicationFactory",
    "ComposeProvider",
    "BuildPolicy",
    "RecipePlan",
    "RecipeResolver",
    "ResolvedRecipe",
    "ResolvedBuild",
    "ResolvedHook",
    "ResolvedHooks",
    "ResolvedMount",
    "ResolvedNetwork",
)


# Compute the dotted module name for one source file.
def module_name(path: Path) -> str:
    # Compute the source-relative parts without the file suffix.
    parts: tuple[str, ...] = path.relative_to(SOURCE_ROOT).with_suffix("").parts

    # Drop the package initializer name.
    if parts[-1] == "__init__":
        # Use the package name.
        parts = parts[:-1]

    # Join the module parts.
    return ".".join(parts)


# Read one source file as text.
def source_of(path: Path) -> str:
    # Return the UTF-8 source.
    return path.read_text(encoding = "utf-8")


# Yield every imported module name from one source text.
def imported_modules(source: str, current: str) -> list[tuple[str, int]]:
    # Parse the source into an abstract syntax tree.
    tree: ast.Module = ast.parse(source)

    # Collect the imported modules.
    imported: list[tuple[str, int]] = []

    # Walk every import node, including lazy imports.
    for node in ast.walk(tree):
        # If the node imports named modules.
        if isinstance(node, ast.Import):
            # Record each imported module.
            for alias in node.names:
                imported.append((alias.name, node.lineno))
        # If the node imports names from a module.
        elif isinstance(node, ast.ImportFrom):
            imported.append((resolve_relative(node, current), node.lineno))

    # Return the imported modules.
    return imported


# Resolve one relative import against its containing module.
def resolve_relative(node: ast.ImportFrom, current: str) -> str:
    # If the import is absolute.
    if node.level == 0:
        # Return the declared module.
        return node.module or ""

    # Compute the package that contains the current module.
    package: list[str] = current.split(".")[:-1]

    # Ascend the parent packages for each relative level beyond the first.
    for _ in range(node.level - 1):
        # Remove one package part.
        package.pop()

    # Append the relative module when present.
    if node.module:
        # Add the module name.
        package.append(node.module)

    # Join the resolved module name.
    return ".".join(package)


# Report whether an imported module matches a declared root.
def matches(module: str, prefixes: frozenset[str] | tuple[str, ...]) -> bool:
    # Check the exact root or a child module.
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


# Return the first package segment for one source path.
def package_of(path: Path) -> str:
    # Compute the relative path below the package root.
    relative: Path = path.relative_to(PACKAGE_ROOT)

    # Return the first directory, or the module name for a root module.
    return relative.parts[0] if len(relative.parts) > 1 else relative.stem


# Yield every production source file.
def production_sources() -> tuple[Path, ...]:
    # Return every Python file under the package.
    return tuple(sorted(PACKAGE_ROOT.rglob("*.py")))


# Verify the package root contains only the initializer and typing metadata.
def test_root_has_no_loose_production_modules() -> None:
    # Collect every root entry.
    entries: set[str] = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file() and path.name != "__pycache__"}

    # Require only the initializer and typing marker at the root.
    assert entries == {"__init__.py", "py.typed"}, entries


# Verify each package imports only its declared lower layers.
def test_packages_import_only_their_declared_layers() -> None:
    # Collect every layering violation.
    violations: list[str] = []

    # Check every production source under a declared layer.
    for path in production_sources():
        # Resolve the first package segment and its rules.
        package: str = package_of(path)
        allowed: frozenset[str] | None = LAYER_RULES.get(package)
        if allowed is None:
            continue

        # Check every imported module.
        for module, line in imported_modules(source_of(path), module_name(path)):
            # Allow standard-library and explicit third-party imports.
            if module.split(".")[0] in sys.stdlib_module_names or not module.startswith("sandbox"):
                continue

            # Allow the declared first-party layers.
            if matches(module, allowed):
                continue

            # Record the forbidden import.
            violations.append(f"{module_name(path)}:{line} imports {module}")

    # Require no cross-layer violations.
    assert violations == []


# Verify Click and Rich stay inside the CLI presentation boundary.
def test_click_and_rich_stay_inside_the_cli() -> None:
    # Collect every presentation dependency violation.
    violations: list[str] = []

    # Check every production source.
    for path in production_sources():
        # Resolve the package and its presentation-relative path.
        package: str = package_of(path)
        relative: str = str(path.relative_to(PACKAGE_ROOT).parent)
        for module, line in imported_modules(source_of(path), module_name(path)):
            # Check the Click boundary.
            if module == "click" and package not in CLICK_PACKAGES:
                violations.append(f"{module_name(path)}:{line} imports click")

            # Check the Rich boundary.
            if module == "rich" and relative not in RICH_PACKAGES:
                violations.append(f"{module_name(path)}:{line} imports rich")

    # Require no Click or Rich import outside the CLI presentation boundary.
    assert violations == []


# Verify no layer imports a backend or privileged implementation package.
def test_no_backend_or_privileged_imports() -> None:
    # Declare the privileged modules and the only layers allowed to import them.
    privileged: dict[str, frozenset[str]] = {
        "sandbox.integrations": frozenset({"composition", "integrations"}),
        "sandbox.composition": frozenset({"composition"}),
        "sandbox.cli": frozenset({"composition", "cli"}),
        "sandbox.sdk": frozenset({"__init__", "cli", "composition", "sdk"}),
        "sandbox.configuration": frozenset({"catalogue", "composition", "configuration", "sdk"}),
        "sandbox.catalogue": frozenset({"composition", "catalogue", "sdk"}),
    }
    backend_roots: tuple[str, ...] = ("docker", "compose")

    # Collect every violation.
    violations: list[str] = []

    # Check every production source.
    for path in production_sources():
        # Resolve the importing layer.
        package: str = package_of(path)
        for module, line in imported_modules(source_of(path), module_name(path)):
            # Reject backend Python packages everywhere.
            if matches(module, backend_roots):
                violations.append(f"{module_name(path)}:{line} imports {module}")

            # Check privileged first-party packages.
            for prefix, allowed in privileged.items():
                if matches(module, (prefix,)) and package not in allowed:
                    violations.append(f"{module_name(path)}:{line} imports {module}")

    # Require no privileged edges.
    assert violations == []


# Verify no production module fails to import.
def test_every_production_module_imports() -> None:
    # Import every module in a fresh interpreter.
    names: str = "\n".join(module_name(path) for path in production_sources())

    # Run the imports with the source tree on the path.
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", "import sys\nfor name in sys.stdin.read().split():\n    __import__(name)\nprint('ok')\n"],
        input = names,
        capture_output = True,
        text = True,
        env = {**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
    )

    # Require every production module.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


# Verify neutral and SDK modules import with adapters and presentation libraries blocked.
def test_neutral_and_sdk_modules_import_with_adapters_blocked() -> None:
    # Declare the guarded package modules.
    guarded: tuple[str, ...] = (
        "sandbox.errors",
        "sandbox.domain",
        "sandbox.ports",
        "sandbox.policy",
        "sandbox.testing",
        "sandbox.sdk",
    )

    # Block adapter and presentation imports before importing any guarded module.
    script: str = """
import sys
BLOCKED = {'docker', 'compose', 'click', 'rich'}
BLOCKED_FIRST_PARTY = {'sandbox.integrations', 'sandbox.composition', 'sandbox.cli'}
class ImportBlocker:
    def find_spec(self, fullname, path = None, target = None):
        if fullname.split('.')[0] in BLOCKED or any(fullname == name or fullname.startswith(name + '.') for name in BLOCKED_FIRST_PARTY):
            raise ImportError(f'blocked import: {fullname}')
        return None
sys.meta_path.insert(0, ImportBlocker())
for name in sys.stdin.read().split():
    __import__(name)
for blocked in ('docker', 'compose', 'click', 'rich', 'sandbox.integrations', 'sandbox.composition', 'sandbox.cli'):
    try:
        __import__(blocked)
    except ImportError:
        continue
    raise SystemExit(f'import blocker allowed: {blocked}')
print('ok')
"""

    # Run the isolated imports with the source tree on the path.
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", script],
        input = "\n".join(guarded),
        capture_output = True,
        text = True,
        env = {**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
    )

    # Require the guarded imports and a proven import blocker.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


# Verify the project module graph has no top-level import cycles.
def test_project_module_graph_has_no_cycles() -> None:
    # Collect the project module names.
    modules: set[str] = {module_name(path) for path in production_sources()}

    # Build the top-level internal dependency graph.
    graph: dict[str, set[str]] = {module: set() for module in modules}
    for path in production_sources():
        # Read only the module body to ignore lazy in-function imports.
        tree: ast.Module = ast.parse(source_of(path))
        current: str = module_name(path)
        for node in tree.body:
            # Resolve absolute and relative imports in the module body.
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [resolve_relative(node, current)]
            for module in imported:
                if module in modules and module != current:
                    graph[current].add(module)

    # Detect cycles with depth-first search.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module: str, path: tuple[str, ...]) -> None:
        # If the module is already on the current path.
        if module in visiting:
            raise AssertionError(f"Import cycle: {' -> '.join((*path, module))}")

        # Skip an already completed module.
        if module in visited:
            return

        # Visit every dependency.
        visiting.add(module)
        for dependency in sorted(graph[module]):
            visit(dependency, (*path, module))
        visiting.remove(module)
        visited.add(module)

    # Visit every module.
    for module in sorted(modules):
        visit(module, ())


# Verify every retired module path is gone.
def test_retired_modules_are_deleted() -> None:
    # Import the utility for locating modules without importing them.
    import importlib.util

    # Require every retired module path to be absent.
    for name in RETIRED_MODULES:
        assert importlib.util.find_spec(name) is None, name


# Verify no retired symbol survives in production source.
def test_retired_symbols_are_absent_from_production_source() -> None:
    # Collect every occurrence of a retired symbol.
    found: list[str] = []
    for path in production_sources():
        source: str = source_of(path)
        for symbol in RETIRED_SYMBOLS:
            # Check whole-word occurrences.
            if symbol in source:
                found.append(f"{module_name(path)} contains {symbol}")

    # Require no retired symbol.
    assert found == []


# Verify production code never mutates process-wide environment variables.
def test_production_code_does_not_mutate_process_environment() -> None:
    # Collect every environment mutation.
    found: list[str] = []
    for path in production_sources():
        tree: ast.Module = ast.parse(source_of(path))
        for node in ast.walk(tree):
            # Read the statement line for deterministic diagnostics.
            lineno: int = getattr(node, "lineno", 0)

            # Detect assignments and deletions on `os.environ`.
            targets: list[ast.expr] = []
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            elif isinstance(node, ast.Delete):
                targets = list(node.targets)
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute) and target.value.attr == "environ":
                    found.append(f"{module_name(path)}:{lineno} mutates os.environ")
                if isinstance(target, ast.Attribute) and target.attr in ("environ",) and isinstance(target.value, ast.Name) and target.value.id == "os":
                    found.append(f"{module_name(path)}:{lineno} mutates os.environ")

            # Detect `os.putenv` calls.
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "putenv":
                found.append(f"{module_name(path)}:{lineno} calls os.putenv")

    # Require no process-wide mutation.
    assert found == []
