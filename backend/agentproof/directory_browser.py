"""Pure helper for read-only directory browsing."""

from __future__ import annotations

import os
from pathlib import Path


class DirectoryBrowseError(ValueError):
    """Raised when the requested directory path is invalid."""

    pass


def browse_directory(path_str: str | None) -> tuple[str, str | None, list[tuple[str, str]]]:
    """Return (current_path, parent_path, sorted_child_dirs) for *path_str*.

    *child_dirs* is a list of ``(name, absolute_path)`` tuples for immediate
    child directories, sorted case-insensitively by name.

    Raises ``DirectoryBrowseError`` for invalid input.
    """
    # Resolve the target directory
    target = Path.home() if not path_str or not path_str.strip() else Path(path_str)

    # Expand user home (~)
    target = target.expanduser()

    # Resolve to absolute
    try:
        target = target.resolve()
    except (OSError, ValueError) as exc:
        raise DirectoryBrowseError(
            f"Cannot resolve path: {exc}"
        ) from exc

    # Validate existence and type
    if not target.exists():
        raise DirectoryBrowseError(f"Path does not exist: {target}")

    if not target.is_dir():
        raise DirectoryBrowseError(f"Path is not a directory: {target}")

    # List immediate child directories
    children: list[tuple[str, str]] = []
    try:
        entries = os.scandir(str(target))
    except OSError as exc:
        raise DirectoryBrowseError(
            f"Cannot inspect directory: {exc}"
        ) from exc

    with entries:
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                # Skip entries that cannot be inspected
                continue
            if is_dir:
                try:
                    resolved = Path(entry.path).resolve()
                except (OSError, RuntimeError, ValueError):
                    continue
                children.append((entry.name, str(resolved)))

    # Sort case-insensitively by display name
    children.sort(key=lambda pair: pair[0].casefold())

    # Compute parent_path
    parent = target.parent
    if parent == target:
        # We are at the filesystem root
        parent_path: str | None = None
    else:
        parent_path = str(parent)

    return str(target), parent_path, children
