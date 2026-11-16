# Imports.
from pathlib import Path

# Import the manifest locator.
from sandbox.catalogue.manifest import CATALOGUE_MANIFEST_FILENAME, manifest_path

# Import errors.
from sandbox.errors import CatalogueInstallError


# Resolve one catalogue root inside a materialized source.
class SourceLayout:
    # Source root.
    root: Path

    # Report whether one directory contains a catalogue manifest.
    def _contains_manifest(self: "SourceLayout", directory: Path) -> bool:
        # Return whether the manifest is a regular file.
        return manifest_path(directory).is_file()

    # List immediate child catalogue roots in deterministic name order.
    def _list_catalogue_directories(self: "SourceLayout") -> tuple[Path, ...]:
        # Prepare the candidate directories.
        candidates: list[Path] = []

        # For each immediate child of the source root.
        for child in self.root.iterdir():
            # If the child is a real directory with a manifest.
            if child.is_dir() and not child.is_symlink() and self._contains_manifest(child):
                # Retain the child.
                candidates.append(child)

        # Sort the candidates by name.
        candidates.sort(key = lambda candidate: candidate.name)

        # Return the candidates.
        return tuple(candidates)

    # Resolve an explicitly selected catalogue directory.
    def _provide_selected_catalogue(self: "SourceLayout", which: str) -> Path:
        # If the selector is blank.
        if not which.strip():
            # Throw.
            raise CatalogueInstallError("The catalogue selector must be a nonblank relative directory.")

        # Interpret the selector relative to the source.
        selector: Path = Path(which)

        # If the selector is absolute.
        if selector.is_absolute():
            # Throw.
            raise CatalogueInstallError(f"Catalogue selector `{which}` must be a relative directory.")

        # Resolve the selected path and enforce the source boundary.
        selected: Path = (self.root / selector).resolve()

        # If the selected path escapes the source.
        if not selected.is_relative_to(self.root):
            # Throw.
            raise CatalogueInstallError(f"Catalogue selector `{which}` must resolve inside the catalogue source.")

        # If the selected path is not a directory.
        if not selected.is_dir():
            # Throw.
            raise CatalogueInstallError(f"Catalogue selector `{which}` does not identify a directory in the source.")

        # If the selected directory has no manifest.
        if not self._contains_manifest(selected):
            # Throw.
            raise CatalogueInstallError(f"Catalogue selector `{which}` does not contain `{CATALOGUE_MANIFEST_FILENAME}`.")

        # Return the selected catalogue root.
        return selected

    # Format a nonempty list as a human-readable enumeration.
    def _list_to_prose(self: "SourceLayout", values: list[str]) -> str:
        # Quote each value.
        quoted: list[str] = [f"`{value}`" for value in values]

        # If there is one value.
        if len(quoted) == 1:
            # Return the value.
            return quoted[0]

        # If there are two values.
        if len(quoted) == 2:
            # Return the joined values.
            return f"{quoted[0]} and {quoted[1]}"

        # Return the enumeration.
        return ", ".join(quoted[:-1]) + f", and {quoted[-1]}"

    # Initialize the source layout.
    def __init__(self: "SourceLayout", root: Path) -> None:
        # Resolve and retain the source root.
        self.root = root.resolve()

    # Resolve the catalogue root selected by an explicit directory or layout.
    def resolve(self: "SourceLayout", which: str | None) -> Path:
        # If the caller supplied an explicit selector.
        if which is not None:
            # Return the selected catalogue root.
            return self._provide_selected_catalogue(which)

        # Determine whether the source root is itself a catalogue.
        root_is_catalogue: bool = self._contains_manifest(self.root)

        # Locate immediate child catalogues.
        candidates: tuple[Path, ...] = self._list_catalogue_directories()

        # If the source root is the only catalogue.
        if root_is_catalogue and not candidates:
            # Return the source root.
            return self.root

        # If child catalogues exist.
        if candidates:
            # Format the candidate names.
            names: str = self._list_to_prose([candidate.name for candidate in candidates])

            # If the source root is also a catalogue.
            if root_is_catalogue:
                # Throw.
                raise CatalogueInstallError(f"Source root is a catalogue, but also contains the child catalogues {names}. Use `--which .` to install for the root catalogue, or `--which <directory>` to install a child catalogue.")

            # Throw.
            raise CatalogueInstallError(f"Source root does not contain `{CATALOGUE_MANIFEST_FILENAME}`. Available catalogues are {names}. Use `--which <directory>` to select one.")

        # Throw when the source contains no catalogue at the scanned depth.
        raise CatalogueInstallError(f"Source root does not contain `{CATALOGUE_MANIFEST_FILENAME}`, and no immediate child catalogue was found. Use `--which <directory>` to select a nested catalogue.")
