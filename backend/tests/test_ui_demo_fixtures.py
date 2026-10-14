"""Keep the GitHub demo inputs aligned with their documented outcomes."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "demo_fixtures"


def _run(*command: str, cwd: Path, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _baseline(name: str, tmp_path: Path) -> Path:
    repository = tmp_path / name
    shutil.copytree(FIXTURES / name, repository)
    _run("git", "init", "--quiet", cwd=repository)
    _run("git", "add", ".", cwd=repository)
    _run(
        "git",
        "-c",
        "user.name=AgentProof Demo",
        "-c",
        "user.email=demo@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Approved demo baseline",
        cwd=repository,
    )
    return repository


def _apply_patch(repository: Path, name: str) -> None:
    patch = FIXTURES / "changes" / f"{name}.patch"
    _run("git", "apply", "--check", str(patch), cwd=repository)
    _run("git", "apply", str(patch), cwd=repository)


def test_public_dateutil_demo_keeps_tests_and_adds_empty_input_error(
    tmp_path: Path,
) -> None:
    repository = _baseline("public_dateutil_empty_input", tmp_path)
    _run(sys.executable, "-m", "pytest", "-q", cwd=repository)

    _apply_patch(repository, "public_dateutil_empty_input")
    _run(sys.executable, "-m", "pytest", "-q", cwd=repository)
    result = _run(
        sys.executable,
        "-c",
        "from datetime import date; from parser import parse_date; "
        "parse_date(' ', date(2000, 1, 1))",
        cwd=repository,
        expected=1,
    )
    assert "ValueError: empty date input" in result.stderr


def test_deleted_test_demo_passes_candidate_suite_but_fails_approved_test(
    tmp_path: Path,
) -> None:
    repository = _baseline("unsafe_deleted_test", tmp_path)
    _run(sys.executable, "-m", "pytest", "-q", cwd=repository)

    _apply_patch(repository, "unsafe_deleted_test")
    assert not (repository / "tests" / "test_large_non_member.py").exists()
    _run(sys.executable, "-m", "pytest", "-q", cwd=repository)

    approved_test = _run(
        "git", "show", "HEAD:tests/test_large_non_member.py", cwd=repository
    ).stdout
    (repository / "tests" / "test_large_non_member.py").write_text(
        approved_test, encoding="utf-8"
    )
    failed = _run(sys.executable, "-m", "pytest", "-q", cwd=repository, expected=1)
    assert "test_large_non_member_does_not_get_member_discount" in failed.stdout
