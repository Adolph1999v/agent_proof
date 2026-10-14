"""The demo setup command must create fresh repos without changing existing ones."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.prepare_ui_demos import CASE_NAMES, FIXTURE_ROOT, prepare


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def test_prepare_creates_independent_clean_repositories_and_patches(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "demo projects"
    assert prepare(destination) == destination

    for name in CASE_NAMES:
        repository = destination / name
        assert (repository / ".git").is_dir()
        assert _git(repository, "status", "--porcelain") == ""
        assert _git(repository, "rev-parse", "--show-toplevel") == str(repository)
        patch = destination / "changes" / f"{name}.patch"
        assert patch.read_bytes() == (FIXTURE_ROOT / "changes" / patch.name).read_bytes()
        _git(repository, "apply", "--check", str(patch))


def test_prepare_refuses_to_replace_a_modified_demo(tmp_path: Path) -> None:
    destination = tmp_path / "demo projects"
    prepare(destination)
    changed_file = destination / "public_dateutil_empty_input" / "parser.py"
    changed_file.write_text("user's work\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        prepare(destination)

    assert changed_file.read_text(encoding="utf-8") == "user's work\n"
