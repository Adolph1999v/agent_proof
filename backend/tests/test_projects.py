import json
import shutil
import subprocess
from pathlib import Path

import pytest
from agentproof.models import AutomaticVerificationRequest, BaselineApprovalRequest
from agentproof.projects import ProjectInputError, ProjectStore
from agentproof.verifier import DeterministicVerifier


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def create_repository(parent: Path, name: str, return_value: int = 1) -> Path:
    repository = parent / name
    (repository / "tests").mkdir(parents=True)
    (repository / "service.py").write_text(
        f"def value() -> int:\n    return {return_value}\n",
        encoding="utf-8",
    )
    (repository / "tests" / "test_service.py").write_text(
        f"from service import value\n\n\ndef test_value() -> None:\n"
        f"    assert value() == {return_value}\n",
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


def approve(store: ProjectStore, repository: Path, digest: str, task: str = "Initial state"):
    return store.approve_baseline(
        BaselineApprovalRequest(
            repository_path=str(repository),
            expected_current_digest=digest,
            task=task,
        )
    )


def test_baseline_history_and_automatic_verification_are_project_scoped(tmp_path: Path) -> None:
    repository = create_repository(tmp_path, "alpha")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    verifier = DeterministicVerifier(tmp_path / "state" / "runs")

    first_inspection = store.inspect(str(repository))
    assert first_inspection.baseline_count == 0
    assert first_inspection.current_state_audit is not None
    assert first_inspection.current_state_audit.status == "passed"

    first_approval = approve(store, repository, first_inspection.current_digest)
    (repository / "service.py").write_text(
        '"""Service values."""\n\n\ndef value() -> int:\n    return 1\n',
        encoding="utf-8",
    )
    changed = store.inspect(str(repository))
    assert [(change.path, change.status) for change in changed.changes] == [
        ("service.py", "modified")
    ]

    report = store.verify_automatic(
        AutomaticVerificationRequest(
            repository_path=str(repository),
            task="Document the service without changing its behavior.",
        ),
        verifier,
    )

    assert report.verdict == "INCONCLUSIVE"
    assert report.repository_id == first_inspection.repository_id
    assert report.baseline_id == first_approval.baseline.baseline_id
    assert report.change_source == "approved_baseline"
    assert report.test_execution.status == "passed"
    assert report.changed_files[0].path == "service.py"

    second_approval = approve(
        store,
        repository,
        changed.current_digest,
        task="Approved documented service",
    )
    assert second_approval.baseline.parent_baseline_id == first_approval.baseline.baseline_id
    assert second_approval.project.baseline_count == 2


def test_different_repositories_never_share_identity_or_baselines(tmp_path: Path) -> None:
    alpha = create_repository(tmp_path, "alpha", return_value=1)
    beta = create_repository(tmp_path, "beta", return_value=2)
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")

    alpha_inspection = store.inspect(str(alpha))
    beta_inspection = store.inspect(str(beta))
    alpha_baseline = approve(store, alpha, alpha_inspection.current_digest).baseline
    beta_baseline = approve(store, beta, beta_inspection.current_digest).baseline

    assert alpha_inspection.repository_id != beta_inspection.repository_id
    assert alpha_baseline.repository_id == alpha_inspection.repository_id
    assert beta_baseline.repository_id == beta_inspection.repository_id
    assert alpha_baseline.baseline_id != beta_baseline.baseline_id


def test_moved_repository_keeps_identity_and_history(tmp_path: Path) -> None:
    original = create_repository(tmp_path, "before-move")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    initial = store.inspect(str(original))
    approved = approve(store, original, initial.current_digest).baseline
    moved = tmp_path / "after-move"
    original.rename(moved)

    after_move = store.inspect(str(moved))

    assert after_move.repository_id == initial.repository_id
    assert after_move.path_changed is True
    assert after_move.latest_baseline is not None
    assert after_move.latest_baseline.baseline_id == approved.baseline_id


def test_copied_identity_is_rejected_while_original_path_exists(tmp_path: Path) -> None:
    original = create_repository(tmp_path, "original")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    store.inspect(str(original))
    copied = tmp_path / "copied"
    shutil.copytree(original, copied)

    with pytest.raises(ProjectInputError, match="active at another path"):
        store.inspect(str(copied))


def test_approval_rejects_stale_or_duplicate_project_state(tmp_path: Path) -> None:
    repository = create_repository(tmp_path, "stale")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    inspection = store.inspect(str(repository))
    (repository / "service.py").write_text("def value() -> int:\n    return 3\n", encoding="utf-8")

    with pytest.raises(ProjectInputError, match="changed after inspection"):
        approve(store, repository, inspection.current_digest)

    current = store.inspect(str(repository))
    approve(store, repository, current.current_digest)
    with pytest.raises(ProjectInputError, match="already the latest"):
        approve(store, repository, current.current_digest)


def test_change_discovery_reports_renames_additions_and_deletions(tmp_path: Path) -> None:
    repository = create_repository(tmp_path, "change-kinds")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    initial = store.inspect(str(repository))
    approve(store, repository, initial.current_digest)
    (repository / "service.py").rename(repository / "renamed_service.py")
    (repository / "notes.md").write_text("new evidence\n", encoding="utf-8")
    (repository / "tests" / "test_service.py").unlink()

    changed = store.inspect(str(repository))
    change_values = {
        (change.path, change.status, change.previous_path) for change in changed.changes
    }

    assert ("renamed_service.py", "renamed", "service.py") in change_values
    assert ("notes.md", "added", None) in change_values
    assert ("tests/test_service.py", "deleted", None) in change_values


def test_inspection_returns_safe_before_and_after_previews(tmp_path: Path) -> None:
    repository = create_repository(tmp_path, "change-previews")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    initial = store.inspect(str(repository))
    approve(store, repository, initial.current_digest)

    (repository / "service.py").write_text(
        "def value() -> int:\n    return 2\n",
        encoding="utf-8",
    )
    (repository / "notes.md").write_text("new explanation\n", encoding="utf-8")
    (repository / "image.bin").write_bytes(b"\x00\x01\x02")
    (repository / "tests" / "test_service.py").unlink()

    inspection = store.inspect(str(repository))
    previews = {preview.path: preview for preview in inspection.change_previews}

    assert previews["service.py"].before.state == "text"
    assert previews["service.py"].before.content == "def value() -> int:\n    return 1\n"
    assert previews["service.py"].after.content == "def value() -> int:\n    return 2\n"
    assert previews["notes.md"].before.state == "missing"
    assert previews["notes.md"].after.content == "new explanation\n"
    assert previews["tests/test_service.py"].before.content is not None
    assert previews["tests/test_service.py"].after.state == "missing"
    assert previews["image.bin"].after.state == "binary"
    assert previews["image.bin"].after.content is None


def test_non_git_folder_keeps_identity_after_a_move(tmp_path: Path) -> None:
    original = tmp_path / "plain-folder"
    original.mkdir()
    (original / "notes.txt").write_text("approved state\n", encoding="utf-8")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    initial = store.inspect(str(original))
    approved = approve(store, original, initial.current_digest).baseline
    moved = tmp_path / "moved-plain-folder"
    original.rename(moved)

    after_move = store.inspect(str(moved))

    assert after_move.repository_id == initial.repository_id
    assert after_move.path_changed is True
    assert after_move.latest_baseline is not None
    assert after_move.latest_baseline.baseline_id == approved.baseline_id


def test_cross_project_baseline_manifest_is_rejected(tmp_path: Path) -> None:
    projects_root = tmp_path / "state" / "projects"
    store = ProjectStore(projects_root, tmp_path / "state" / "audits")
    alpha = create_repository(tmp_path, "manifest-alpha")
    beta = create_repository(tmp_path, "manifest-beta")
    alpha_inspection = store.inspect(str(alpha))
    beta_inspection = store.inspect(str(beta))
    approve(store, alpha, alpha_inspection.current_digest)
    beta_approval = approve(store, beta, beta_inspection.current_digest)
    manifest_path = (
        projects_root
        / beta_inspection.repository_id
        / "baselines"
        / f"{beta_approval.baseline.baseline_id}.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary"]["repository_id"] = alpha_inspection.repository_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ProjectInputError, match="cross-project"):
        store.inspect(str(beta))


def test_corrupted_baseline_object_is_rejected(tmp_path: Path) -> None:
    projects_root = tmp_path / "state" / "projects"
    store = ProjectStore(projects_root, tmp_path / "state" / "audits")
    repository = create_repository(tmp_path, "corrupted-object")
    inspection = store.inspect(str(repository))
    approval = approve(store, repository, inspection.current_digest)
    manifest_path = (
        projects_root
        / inspection.repository_id
        / "baselines"
        / f"{approval.baseline.baseline_id}.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_digest = next(iter(manifest["entries"].values()))["sha256"]
    (projects_root / inspection.repository_id / "objects" / first_digest).write_text(
        "tampered",
        encoding="utf-8",
    )

    with pytest.raises(ProjectInputError, match="object is missing or corrupted"):
        store.inspect(str(repository))


def test_unrelated_git_lineage_is_not_compared_to_latest_baseline(tmp_path: Path) -> None:
    repository = create_repository(tmp_path, "lineage")
    store = ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits")
    inspection = store.inspect(str(repository))
    approve(store, repository, inspection.current_digest)
    run_git(repository, "checkout", "--orphan", "unrelated")
    run_git(
        repository,
        "-c",
        "user.name=AgentProof Tests",
        "-c",
        "user.email=tests@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Unrelated root",
    )

    with pytest.raises(ProjectInputError, match="unrelated lineages"):
        store.inspect(str(repository))
