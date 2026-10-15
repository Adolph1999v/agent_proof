import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.evaluate import (
    DEFAULT_OUTPUT,
    FILTERED_OUTPUT,
    RECORDED_OUTPUT,
    _prepare_case,
    _resolve_output,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_evaluation_manifest_has_eleven_unique_cases_with_public_provenance() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "evaluation" / "benchmark_cases.json").read_text(encoding="utf-8")
    )
    cases = manifest["cases"]

    assert len(cases) == 11
    assert len({case["id"] for case in cases}) == 11
    assert sum(case["expected"] == "VERIFIED" for case in cases) == 6
    assert sum(case["expected"] == "UNSAFE" for case in cases) == 5
    assert any(case["difficulty"] == "challenging" for case in cases)
    assert any(case["difficulty"] == "adversarial" for case in cases)
    public_cases = [case for case in cases if case["difficulty"] == "public-bug-derived"]
    assert len(public_cases) == 1
    assert public_cases[0]["source"]["issue_url"].startswith("https://github.com/")


def test_every_evaluation_case_builds_a_clean_repo_and_nonempty_patch(tmp_path: Path) -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "evaluation" / "benchmark_cases.json").read_text(encoding="utf-8")
    )

    for index, case in enumerate(manifest["cases"]):
        repository, patch = _prepare_case(case, tmp_path / f"case-{index}")
        assert (repository / ".git").is_dir()
        assert patch.strip()


def test_evaluation_outputs_do_not_overwrite_recorded_result(tmp_path: Path) -> None:
    assert DEFAULT_OUTPUT.parent == PROJECT_ROOT / "artifacts" / "evaluation"
    assert DEFAULT_OUTPUT != RECORDED_OUTPUT
    assert _resolve_output(None, None) == DEFAULT_OUTPUT
    assert _resolve_output(None, ["one-case"]) == FILTERED_OUTPUT
    assert _resolve_output(tmp_path / "custom.json", ["one-case"]) == tmp_path / "custom.json"
    with pytest.raises(ValueError, match="cannot be overwritten"):
        _resolve_output(RECORDED_OUTPUT, None)


def test_cli_rejects_recorded_result_before_running_cases() -> None:
    original = RECORDED_OUTPUT.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate.py",
            "--output",
            str(RECORDED_OUTPUT),
        ],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "cannot be overwritten" in result.stderr
    assert "[1/11]" not in result.stdout
    assert RECORDED_OUTPUT.read_bytes() == original
