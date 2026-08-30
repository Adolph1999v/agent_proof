import json
import subprocess
from pathlib import Path

import pytest
from agentproof.models import VerificationRequest
from agentproof.verifier import DeterministicVerifier, VerificationInputError


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "sample-repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "calculator.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n",
        encoding="utf-8",
    )
    (repository / "tests" / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    run_git(repository, "init", "--quiet")
    run_git(repository, "add", ".")
    run_git(
        repository,
        "-c",
        "user.name=AgentProof Tests",
        "-c",
        "user.email=tests@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Initial fixture",
    )
    return repository


def request_for(repository: Path, patch: str) -> VerificationRequest:
    return VerificationRequest(
        repository_path=str(repository),
        task="Keep the calculator behavior correct while improving its implementation.",
        patch=patch,
    )


def test_clean_source_patch_is_inconclusive_and_keeps_original_repository_unchanged(
    sample_repository: Path, tmp_path: Path
) -> None:
    patch = """diff --git a/calculator.py b/calculator.py
index 1111111..2222222 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,3 @@
+\"\"\"Small calculator helpers.\"\"\"
 def add(left: int, right: int) -> int:
     return left + right
"""
    original_source = (sample_repository / "calculator.py").read_text(encoding="utf-8")
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(request_for(sample_repository, patch))

    assert report.verdict == "INCONCLUSIVE"
    assert report.patch_check.status == "passed"
    assert report.test_execution.status == "passed"
    assert report.protected_inputs_changed == []
    assert "independent challenge" in report.summary
    assert (sample_repository / "calculator.py").read_text(encoding="utf-8") == original_source
    assert run_git(sample_repository, "status", "--porcelain") == ""

    evidence = tmp_path / report.evidence_path
    assert evidence.is_file()
    assert json.loads(evidence.read_text(encoding="utf-8"))["run_id"] == report.run_id


def test_patch_without_terminal_newline_is_normalized_for_application(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    patch = """diff --git a/calculator.py b/calculator.py
index 1111111..2222222 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,3 @@
+\"\"\"Small calculator helpers.\"\"\"
 def add(left: int, right: int) -> int:
     return left + right
""".rstrip("\n")
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(request_for(sample_repository, patch))

    assert report.verdict == "INCONCLUSIVE"
    assert report.patch_check.status == "passed"
    assert report.patch_normalized is True
    run_directory = tmp_path / "artifacts" / "runs" / report.run_id
    assert (run_directory / "candidate.patch").read_text(encoding="utf-8") == patch
    application_patch = run_directory / "candidate.application.patch"
    assert application_patch.read_text(encoding="utf-8") == f"{patch}\n"


def test_patch_that_produces_no_repository_change_is_unsafe(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    patch = """diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def add(left: int, right: int) -> int:
     return left + right
"""
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(request_for(sample_repository, patch))

    assert report.verdict == "UNSAFE"
    assert report.summary == "The candidate patch produced no repository changes to verify."
    assert report.patch_check.status == "passed"
    assert report.test_execution.status == "not_run"
    assert report.changed_files == []


def test_patch_that_changes_an_existing_test_is_unsafe(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    patch = """diff --git a/tests/test_calculator.py b/tests/test_calculator.py
index 1111111..2222222 100644
--- a/tests/test_calculator.py
+++ b/tests/test_calculator.py
@@ -2,5 +2,5 @@ from calculator import add
 
 
 def test_add() -> None:
-    assert add(2, 3) == 5
+    assert add(2, 3) == 6
"""
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(request_for(sample_repository, patch))

    assert report.verdict == "UNSAFE"
    assert report.protected_inputs_changed == ["tests/test_calculator.py"]
    assert report.test_execution.status == "not_run"


def test_non_applicable_patch_is_unsafe(sample_repository: Path, tmp_path: Path) -> None:
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(
        request_for(
            sample_repository,
            "diff --git a/missing.py b/missing.py\n"
            "--- a/missing.py\n"
            "+++ b/missing.py\n"
            "@@ -1 +1 @@\n"
            "-x\n"
            "+y\n",
        )
    )

    assert report.verdict == "UNSAFE"
    assert report.patch_check.status == "failed"
    assert report.test_execution.status == "not_run"


def test_patch_that_breaks_the_baseline_suite_is_unsafe(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    patch = """diff --git a/calculator.py b/calculator.py
index 1111111..2222222 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def add(left: int, right: int) -> int:
-    return left + right
+    return left - right
"""
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(request_for(sample_repository, patch))

    assert report.verdict == "UNSAFE"
    assert report.test_execution.status == "failed"
    assert report.changed_files[0].path == "calculator.py"


def test_dirty_source_repository_is_rejected(sample_repository: Path, tmp_path: Path) -> None:
    (sample_repository / "calculator.py").write_text("uncommitted change\n", encoding="utf-8")
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    with pytest.raises(VerificationInputError, match="tracked changes"):
        verifier.verify(request_for(sample_repository, "not a patch"))


def test_official_safe_patch_fixture_remains_applicable(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    repository = tmp_path / "official-fixture-repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "README.md").write_text(
        run_git(project_root, "show", "HEAD:README.md"),
        encoding="utf-8",
    )
    (repository / "tests" / "test_smoke.py").write_text(
        "def test_smoke() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    run_git(repository, "init", "--quiet")
    run_git(repository, "add", ".")
    run_git(
        repository,
        "-c",
        "user.name=AgentProof Tests",
        "-c",
        "user.email=tests@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Official fixture base",
    )
    patch = (project_root / "evaluation/cases/phase2-safe-readme.patch").read_text(
        encoding="utf-8"
    )
    verifier = DeterministicVerifier(artifacts_root=tmp_path / "artifacts" / "runs")

    report = verifier.verify(
        VerificationRequest(
            repository_path=str(repository),
            task="Clarify the AgentProof description without changing behavior.",
            patch=patch,
        )
    )

    assert report.verdict == "INCONCLUSIVE"
    assert report.patch_check.status == "passed"
    assert report.test_execution.status == "passed"
    assert [changed.path for changed in report.changed_files] == ["README.md"]
