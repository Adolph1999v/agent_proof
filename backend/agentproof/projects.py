"""Repository identity, isolated baseline storage, and automatic change discovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agentproof.models import (
    AutomaticVerificationRequest,
    BaselineApprovalRequest,
    BaselineApprovalResponse,
    BaselineSummary,
    CommandEvidence,
    CurrentStateAudit,
    FileVersionPreview,
    ProjectChange,
    ProjectChangePreview,
    ProjectInspection,
    VerificationReport,
    VerificationRequest,
)
from agentproof.verifier import DeterministicVerifier

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECTS_ROOT = PROJECT_ROOT / "artifacts" / "projects"
DEFAULT_AUDITS_ROOT = PROJECT_ROOT / "artifacts" / "audits"
PROJECT_ID_PATTERN = re.compile(r"project-[0-9a-f]{32}")
BASELINE_ID_PATTERN = re.compile(r"baseline-\d{8}T\d{6}Z-[0-9a-f]{8}")
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 250 * 1024 * 1024
MAX_OUTPUT_CHARS = 12_000
MAX_CHANGE_PREVIEWS = 12
MAX_PREVIEW_BYTES = 20_000
EXCLUDED_DIRECTORIES = {
    ".agentproof",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
EXCLUDED_FILES = {".DS_Store"}
PYTEST_CONFIG_NAMES = {"pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"}


class ProjectInputError(ValueError):
    """Raised when project identity or snapshot state cannot be handled safely."""


class _SnapshotEntry(BaseModel):
    sha256: str
    size: int = Field(ge=0)
    executable: bool
    kind: Literal["file", "symlink"]


class _Snapshot(BaseModel):
    digest: str
    file_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    entries: dict[str, _SnapshotEntry]


class _BaselineManifest(BaseModel):
    summary: BaselineSummary
    entries: dict[str, _SnapshotEntry]


class _ProjectRecord(BaseModel):
    repository_id: str
    name: str
    identity_kind: Literal["git", "folder"]
    current_path: str
    known_paths: list[str]
    baseline_ids: list[str] = Field(default_factory=list)
    latest_baseline_id: str | None = None


class ProjectStore:
    """Owns project identities and immutable, per-project baseline histories."""

    def __init__(
        self,
        projects_root: Path = DEFAULT_PROJECTS_ROOT,
        audits_root: Path = DEFAULT_AUDITS_ROOT,
    ) -> None:
        self.projects_root = projects_root
        self.audits_root = audits_root

    def inspect(self, repository_path: str, timeout_seconds: int = 45) -> ProjectInspection:
        root, record, path_changed = self._resolve_project(repository_path, create=True)
        snapshot = self._capture(root, persist_objects=False, repository_id=record.repository_id)
        baseline = self._latest_baseline(record)
        if baseline:
            self._ensure_baseline_compatible(root, record, baseline)
        changes = self._compare(baseline.entries, snapshot.entries) if baseline else []
        audit = self._audit_current_state(root, snapshot, timeout_seconds)
        return self._inspection(
            root,
            record,
            snapshot,
            baseline,
            changes,
            audit,
            path_changed,
        )

    def approve_baseline(self, request: BaselineApprovalRequest) -> BaselineApprovalResponse:
        root, record, path_changed = self._resolve_project(
            request.repository_path,
            create=True,
        )
        snapshot = self._capture(root, persist_objects=True, repository_id=record.repository_id)
        if snapshot.digest != request.expected_current_digest:
            raise ProjectInputError(
                "The project changed after inspection. Inspect it again before approving "
                "a baseline."
            )

        previous = self._latest_baseline(record)
        if previous:
            self._ensure_baseline_compatible(root, record, previous)
        if previous and previous.summary.manifest_digest == snapshot.digest:
            raise ProjectInputError(
                "This exact project state is already the latest approved baseline."
            )

        baseline_id = self._new_identifier("baseline")
        summary = BaselineSummary(
            baseline_id=baseline_id,
            repository_id=record.repository_id,
            created_at=datetime.now(UTC),
            parent_baseline_id=previous.summary.baseline_id if previous else None,
            task=request.task,
            file_count=snapshot.file_count,
            total_bytes=snapshot.total_bytes,
            manifest_digest=snapshot.digest,
            source_commit=self._git_value(root, "rev-parse", "HEAD"),
            evidence_run_id=request.evidence_run_id,
        )
        manifest = _BaselineManifest(summary=summary, entries=snapshot.entries)
        baseline_directory = self._project_directory(record.repository_id) / "baselines"
        baseline_directory.mkdir(parents=True, exist_ok=True)
        self._write_json(
            baseline_directory / f"{baseline_id}.json",
            manifest.model_dump(mode="json"),
        )

        record.baseline_ids.append(baseline_id)
        record.latest_baseline_id = baseline_id
        self._save_record(record)
        project = self._inspection(
            root,
            record,
            snapshot,
            manifest,
            changes=[],
            audit=None,
            path_changed=path_changed,
        )
        return BaselineApprovalResponse(baseline=summary, project=project)

    def verify_automatic(
        self,
        request: AutomaticVerificationRequest,
        verifier: DeterministicVerifier,
    ) -> VerificationReport:
        root, record, _ = self._resolve_project(request.repository_path, create=True)
        baseline = self._latest_baseline(record)
        if baseline is None:
            raise ProjectInputError(
                "This project has no approved baseline. Inspect and approve its current "
                "state first."
            )
        self._ensure_baseline_compatible(root, record, baseline)

        current = self._capture(root, persist_objects=False, repository_id=record.repository_id)
        changes = self._compare(baseline.entries, current.entries)
        if not changes:
            raise ProjectInputError("No changes were detected since the latest approved baseline.")

        preparation_root = self._project_directory(record.repository_id) / "preparations"
        preparation_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=preparation_root, prefix="verify-") as temporary:
            temporary_root = Path(temporary)
            comparison = temporary_root / "comparison"
            source = temporary_root / "source"
            self._materialize_baseline(record.repository_id, baseline, comparison)
            self._initialise_repository(comparison)
            self._replace_with_current(root, current, baseline.entries, comparison)
            self._run_git(comparison, "add", "-A")
            patch = self._run_git(
                comparison,
                "diff",
                "--cached",
                "--binary",
                "--full-index",
                "HEAD",
            )
            if not patch.strip():
                raise ProjectInputError(
                    "The project inventory changed, but no verifiable file change could "
                    "be generated."
                )

            self._materialize_baseline(record.repository_id, baseline, source)
            self._initialise_repository(source)
            report = verifier.verify(
                VerificationRequest(
                    repository_path=str(source),
                    task=request.task,
                    patch=patch,
                    trace=request.trace,
                    timeout_seconds=request.timeout_seconds,
                )
            )

        report.repository = str(root)
        report.repository_id = record.repository_id
        report.baseline_id = baseline.summary.baseline_id
        report.baseline_manifest_digest = baseline.summary.manifest_digest
        report.change_source = "approved_baseline"
        report.source_commit = baseline.summary.source_commit or baseline.summary.manifest_digest
        verifier.persist_report(report)
        return report

    def _resolve_project(
        self,
        requested_path: str,
        *,
        create: bool,
    ) -> tuple[Path, _ProjectRecord, bool]:
        path = Path(requested_path).expanduser().resolve()
        if not path.is_dir():
            raise ProjectInputError("Project path must be an existing directory.")

        git_root = self._git_value(path, "rev-parse", "--show-toplevel")
        if git_root:
            root = Path(git_root).resolve()
            git_directory_value = self._git_value(root, "rev-parse", "--absolute-git-dir")
            if not git_directory_value:
                raise ProjectInputError(
                    "AgentProof could not resolve the repository metadata folder."
                )
            marker = Path(git_directory_value) / "agentproof-project-id"
            identity_kind: Literal["git", "folder"] = "git"
        else:
            root = path
            marker = root / ".agentproof" / "repository-id"
            identity_kind = "folder"

        repository_id = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        if repository_id and not PROJECT_ID_PATTERN.fullmatch(repository_id):
            raise ProjectInputError("The project contains an invalid AgentProof identity marker.")
        if not repository_id:
            if not create:
                raise ProjectInputError("This project has not been registered with AgentProof.")
            repository_id = f"project-{uuid.uuid4().hex}"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"{repository_id}\n", encoding="utf-8")

        record_path = self._project_directory(repository_id) / "project.json"
        if record_path.is_file():
            record = _ProjectRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
            if record.identity_kind != identity_kind:
                raise ProjectInputError(
                    "The stored project identity type does not match this folder."
                )
            other_live_paths = [
                known
                for known in record.known_paths
                if Path(known).resolve() != root and Path(known).exists()
            ]
            if other_live_paths:
                raise ProjectInputError(
                    "This project identity is active at another path. Treat this copy as a new "
                    "workspace or remove the stale identity marker before linking it."
                )
            path_changed = Path(record.current_path).resolve() != root
            record.current_path = str(root)
            if str(root) not in record.known_paths:
                record.known_paths.append(str(root))
        else:
            path_changed = False
            record = _ProjectRecord(
                repository_id=repository_id,
                name=root.name,
                identity_kind=identity_kind,
                current_path=str(root),
                known_paths=[str(root)],
            )
        self._save_record(record)
        return root, record, path_changed

    def _capture(
        self,
        root: Path,
        *,
        persist_objects: bool,
        repository_id: str,
    ) -> _Snapshot:
        entries: dict[str, _SnapshotEntry] = {}
        total_bytes = 0
        object_directory = self._project_directory(repository_id) / "objects"
        if persist_objects:
            object_directory.mkdir(parents=True, exist_ok=True)

        for relative_path in self._project_files(root):
            path = root / relative_path
            if path.is_symlink():
                data = os.readlink(path).encode("utf-8")
                kind: Literal["file", "symlink"] = "symlink"
                executable = False
            else:
                size = path.stat().st_size
                if size > MAX_FILE_BYTES:
                    raise ProjectInputError(
                        f"Snapshot file exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit: "
                        f"{relative_path.as_posix()}"
                    )
                data = path.read_bytes()
                kind = "file"
                executable = bool(path.stat().st_mode & stat.S_IXUSR)

            total_bytes += len(data)
            if total_bytes > MAX_SNAPSHOT_BYTES:
                raise ProjectInputError(
                    f"Project snapshot exceeds the {MAX_SNAPSHOT_BYTES // (1024 * 1024)} MB limit."
                )
            digest = hashlib.sha256(data).hexdigest()
            entries[relative_path.as_posix()] = _SnapshotEntry(
                sha256=digest,
                size=len(data),
                executable=executable,
                kind=kind,
            )
            if persist_objects:
                object_path = object_directory / digest
                if not object_path.exists():
                    object_path.write_bytes(data)

        return _Snapshot(
            digest=self._entries_digest(entries),
            file_count=len(entries),
            total_bytes=total_bytes,
            entries=entries,
        )

    def _project_files(self, root: Path) -> list[Path]:
        git_root = self._git_value(root, "rev-parse", "--show-toplevel")
        if git_root and Path(git_root).resolve() == root:
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "ls-files",
                    "-co",
                    "--exclude-standard",
                    "-z",
                ],
                check=False,
                capture_output=True,
            )
            if completed.returncode != 0:
                raise ProjectInputError("AgentProof could not inventory the Git working tree.")
            candidates = [
                Path(value.decode("utf-8"))
                for value in completed.stdout.split(b"\0")
                if value
            ]
        else:
            candidates = []
            for current, directories, filenames in os.walk(root, followlinks=False):
                current_path = Path(current)
                directories[:] = [
                    name
                    for name in directories
                    if name not in EXCLUDED_DIRECTORIES
                    and not (current_path / name).is_symlink()
                ]
                for filename in filenames:
                    candidates.append((current_path / filename).relative_to(root))

        files: list[Path] = []
        for relative in candidates:
            if (
                relative.name in EXCLUDED_FILES
                or set(relative.parts) & EXCLUDED_DIRECTORIES
                or relative.is_absolute()
                or ".." in relative.parts
            ):
                continue
            path = root / relative
            if path.is_file() or path.is_symlink():
                files.append(relative)
        return sorted(set(files), key=lambda item: item.as_posix())

    def _compare(
        self,
        baseline: dict[str, _SnapshotEntry],
        current: dict[str, _SnapshotEntry],
    ) -> list[ProjectChange]:
        added = set(current) - set(baseline)
        deleted = set(baseline) - set(current)
        modified = {
            path
            for path in set(baseline) & set(current)
            if baseline[path] != current[path]
        }
        changes: list[ProjectChange] = []

        deleted_by_signature: dict[tuple[str, str, bool], list[str]] = {}
        for path in sorted(deleted):
            entry = baseline[path]
            signature = (entry.sha256, entry.kind, entry.executable)
            deleted_by_signature.setdefault(signature, []).append(path)

        renamed_added: set[str] = set()
        renamed_deleted: set[str] = set()
        for path in sorted(added):
            entry = current[path]
            signature = (entry.sha256, entry.kind, entry.executable)
            candidates = deleted_by_signature.get(signature, [])
            if candidates:
                previous = candidates.pop(0)
                renamed_added.add(path)
                renamed_deleted.add(previous)
                changes.append(
                    ProjectChange(path=path, previous_path=previous, status="renamed")
                )

        changes.extend(
            ProjectChange(path=path, status="added") for path in sorted(added - renamed_added)
        )
        changes.extend(ProjectChange(path=path, status="modified") for path in sorted(modified))
        changes.extend(
            ProjectChange(path=path, status="deleted")
            for path in sorted(deleted - renamed_deleted)
        )
        return sorted(changes, key=lambda change: (change.path, change.status))

    def _change_previews(
        self,
        root: Path,
        repository_id: str,
        baseline: _BaselineManifest,
        current: _Snapshot,
        changes: list[ProjectChange],
    ) -> list[ProjectChangePreview]:
        previews: list[ProjectChangePreview] = []
        for change in changes[:MAX_CHANGE_PREVIEWS]:
            before_path = change.previous_path or change.path
            previews.append(
                ProjectChangePreview(
                    path=change.path,
                    status=change.status,
                    previous_path=change.previous_path,
                    before=self._baseline_file_preview(
                        repository_id,
                        before_path,
                        baseline.entries.get(before_path),
                    ),
                    after=self._current_file_preview(
                        root,
                        change.path,
                        current.entries.get(change.path),
                    ),
                )
            )
        return previews

    def _baseline_file_preview(
        self,
        repository_id: str,
        relative_path: str,
        entry: _SnapshotEntry | None,
    ) -> FileVersionPreview:
        if entry is None:
            return FileVersionPreview(path=relative_path, state="missing")
        object_path = self._project_directory(repository_id) / "objects" / entry.sha256
        if not object_path.is_file() or self._sha256_file(object_path) != entry.sha256:
            raise ProjectInputError("A baseline preview object is missing or corrupted.")
        return self._file_preview(relative_path, entry, object_path.read_bytes())

    def _current_file_preview(
        self,
        root: Path,
        relative_path: str,
        entry: _SnapshotEntry | None,
    ) -> FileVersionPreview:
        if entry is None:
            return FileVersionPreview(path=relative_path, state="missing")
        path = root / self._safe_relative_path(relative_path)
        if entry.kind == "symlink":
            if not path.is_symlink():
                raise ProjectInputError("The project changed while preparing its preview.")
            data = os.readlink(path).encode("utf-8")
        else:
            if not path.is_file():
                raise ProjectInputError("The project changed while preparing its preview.")
            data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise ProjectInputError("The project changed while preparing its preview.")
        return self._file_preview(relative_path, entry, data)

    @staticmethod
    def _file_preview(
        relative_path: str,
        entry: _SnapshotEntry,
        data: bytes,
    ) -> FileVersionPreview:
        if entry.kind == "symlink":
            return FileVersionPreview(
                path=relative_path,
                state="symlink",
                content=data.decode("utf-8", errors="replace"),
            )
        if b"\0" in data:
            return FileVersionPreview(path=relative_path, state="binary")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return FileVersionPreview(path=relative_path, state="binary")
        truncated = len(data) > MAX_PREVIEW_BYTES
        if truncated:
            text = data[:MAX_PREVIEW_BYTES].decode("utf-8", errors="ignore")
        return FileVersionPreview(
            path=relative_path,
            state="text",
            content=text,
            truncated=truncated,
        )

    def _audit_current_state(
        self,
        root: Path,
        snapshot: _Snapshot,
        timeout_seconds: int,
    ) -> CurrentStateAudit:
        audit_id = self._new_identifier("audit")
        audit_directory = self.audits_root / audit_id
        workspace = audit_directory / "workspace"
        audit_directory.mkdir(parents=True, exist_ok=False)
        self._copy_current(root, snapshot.entries, workspace)
        self._initialise_repository(workspace)

        supports_pytest = any(
            path.endswith(".py") and self._is_test_path(Path(path)) for path in snapshot.entries
        ) or any(Path(path).name in PYTEST_CONFIG_NAMES for path in snapshot.entries)
        if supports_pytest:
            evidence = self._run_command(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=workspace,
                timeout_seconds=timeout_seconds,
            )
            status = evidence.status
            summary = {
                "passed": "Current pytest checks pass in the disposable audit workspace.",
                "failed": "Current pytest checks fail in the disposable audit workspace.",
                "timed_out": "Current pytest checks timed out in the disposable audit workspace.",
                "not_run": "Current pytest checks were not run.",
            }[status]
        else:
            status = "not_supported"
            summary = "No supported pytest checks were found for the current-state audit."
            evidence = CommandEvidence(
                status="not_run",
                output_preview="Phase 2.5 currently supports the fixed pytest audit adapter only.",
            )

        audit = CurrentStateAudit(
            status=status if status != "not_run" else "not_supported",
            summary=summary,
            test_execution=evidence,
            evidence_path=f"artifacts/audits/{audit_id}/audit.json",
        )
        self._write_json(audit_directory / "audit.json", audit.model_dump(mode="json"))
        return audit

    def _inspection(
        self,
        root: Path,
        record: _ProjectRecord,
        snapshot: _Snapshot,
        baseline: _BaselineManifest | None,
        changes: list[ProjectChange],
        audit: CurrentStateAudit | None,
        path_changed: bool,
    ) -> ProjectInspection:
        return ProjectInspection(
            repository_id=record.repository_id,
            name=record.name,
            current_path=record.current_path,
            path_changed=path_changed,
            identity_kind=record.identity_kind,
            current_digest=snapshot.digest,
            current_file_count=snapshot.file_count,
            baseline_count=len(record.baseline_ids),
            latest_baseline=baseline.summary if baseline else None,
            changes=changes,
            change_previews=(
                self._change_previews(
                    root,
                    record.repository_id,
                    baseline,
                    snapshot,
                    changes,
                )
                if baseline
                else []
            ),
            current_state_audit=audit,
        )

    def _latest_baseline(self, record: _ProjectRecord) -> _BaselineManifest | None:
        if not record.latest_baseline_id:
            return None
        if not BASELINE_ID_PATTERN.fullmatch(record.latest_baseline_id):
            raise ProjectInputError("The latest baseline identifier is invalid.")
        path = (
            self._project_directory(record.repository_id)
            / "baselines"
            / f"{record.latest_baseline_id}.json"
        )
        if not path.is_file():
            raise ProjectInputError("The latest baseline manifest is missing.")
        manifest = _BaselineManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if manifest.summary.repository_id != record.repository_id:
            raise ProjectInputError("A cross-project baseline reference was rejected.")
        if self._entries_digest(manifest.entries) != manifest.summary.manifest_digest:
            raise ProjectInputError("The latest baseline manifest is corrupted.")
        object_directory = self._project_directory(record.repository_id) / "objects"
        for digest in {entry.sha256 for entry in manifest.entries.values()}:
            object_path = object_directory / digest
            if not object_path.is_file() or self._sha256_file(object_path) != digest:
                raise ProjectInputError("A baseline object is missing or corrupted.")
        return manifest

    def _ensure_baseline_compatible(
        self,
        root: Path,
        record: _ProjectRecord,
        baseline: _BaselineManifest,
    ) -> None:
        source_commit = baseline.summary.source_commit
        if record.identity_kind != "git" or not source_commit:
            return
        completed = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", source_commit, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if completed.returncode != 0:
            raise ProjectInputError(
                "The latest approved baseline is not compatible with the current Git "
                "history. AgentProof refused to compare unrelated lineages."
            )

    def _materialize_baseline(
        self,
        repository_id: str,
        manifest: _BaselineManifest,
        destination: Path,
    ) -> None:
        if manifest.summary.repository_id != repository_id:
            raise ProjectInputError("A cross-project baseline reference was rejected.")
        object_directory = self._project_directory(repository_id) / "objects"
        destination.mkdir(parents=True, exist_ok=False)
        for relative_value, entry in manifest.entries.items():
            relative = self._safe_relative_path(relative_value)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            object_path = object_directory / entry.sha256
            if not object_path.is_file() or self._sha256_file(object_path) != entry.sha256:
                raise ProjectInputError("A baseline object is missing or corrupted.")
            if entry.kind == "symlink":
                link_target = object_path.read_text(encoding="utf-8")
                if Path(link_target).is_absolute() or ".." in Path(link_target).parts:
                    raise ProjectInputError("An unsafe baseline symlink was rejected.")
                target.symlink_to(link_target)
            else:
                shutil.copyfile(object_path, target)
                target.chmod(0o755 if entry.executable else 0o644)

    def _replace_with_current(
        self,
        root: Path,
        current: _Snapshot,
        baseline_entries: dict[str, _SnapshotEntry],
        destination: Path,
    ) -> None:
        for relative_value in sorted(
            baseline_entries,
            key=lambda value: len(Path(value).parts),
            reverse=True,
        ):
            target = destination / self._safe_relative_path(relative_value)
            if target.is_symlink() or target.is_file():
                target.unlink()
        self._copy_current(root, current.entries, destination)

    def _copy_current(
        self,
        root: Path,
        entries: dict[str, _SnapshotEntry],
        destination: Path,
    ) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for relative_value, entry in entries.items():
            relative = self._safe_relative_path(relative_value)
            source = root / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                link_target = os.readlink(source)
                if Path(link_target).is_absolute() or ".." in Path(link_target).parts:
                    raise ProjectInputError("An unsafe project symlink was rejected.")
                target.symlink_to(link_target)
                data = link_target.encode("utf-8")
            else:
                shutil.copyfile(source, target)
                target.chmod(0o755 if entry.executable else 0o644)
                data = target.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry.sha256:
                raise ProjectInputError(
                    "The project changed while AgentProof was preparing its disposable workspace."
                )

    def _initialise_repository(self, root: Path) -> None:
        self._run_git(root, "init", "--quiet")
        self._run_git(root, "add", "-A")
        self._run_git(
            root,
            "-c",
            "user.name=AgentProof",
            "-c",
            "user.email=local@agentproof.invalid",
            "commit",
            "--quiet",
            "-m",
            "Approved AgentProof baseline",
        )

    def _save_record(self, record: _ProjectRecord) -> None:
        directory = self._project_directory(record.repository_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "project.json", record.model_dump(mode="json"))

    def _project_directory(self, repository_id: str) -> Path:
        if not PROJECT_ID_PATTERN.fullmatch(repository_id):
            raise ProjectInputError("Invalid AgentProof repository identity.")
        return self.projects_root / repository_id

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _safe_relative_path(value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ProjectInputError("A snapshot contained an unsafe file path.")
        return path

    @staticmethod
    def _new_identifier(prefix: str) -> str:
        return f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _entries_digest(entries: dict[str, _SnapshotEntry]) -> str:
        canonical = json.dumps(
            {path: entry.model_dump(mode="json") for path, entry in sorted(entries.items())},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_test_path(path: Path) -> bool:
        lowered_parts = {part.lower() for part in path.parts}
        name = path.name.lower()
        return (
            bool({"test", "tests", "__tests__"} & lowered_parts)
            or name.startswith("test_")
            or name.endswith("_test.py")
        )

    @staticmethod
    def _git_value(root: Path, *arguments: str) -> str | None:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    @staticmethod
    def _run_git(root: Path, *arguments: str) -> str:
        environment = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_TERMINAL_PROMPT": "0",
        }
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        if completed.returncode != 0:
            raise ProjectInputError(completed.stdout or completed.stderr or "Git command failed.")
        return completed.stdout

    @staticmethod
    def _run_command(command: list[str], *, cwd: Path, timeout_seconds: int) -> CommandEvidence:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return CommandEvidence(
                command=command,
                status="timed_out",
                duration_ms=round((time.monotonic() - started) * 1000),
                output_preview=(f"{output}\nTimed out after {timeout_seconds} seconds.")[
                    :MAX_OUTPUT_CHARS
                ],
            )
        return CommandEvidence(
            command=command,
            status="passed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            duration_ms=round((time.monotonic() - started) * 1000),
            output_preview=(completed.stdout or "")[:MAX_OUTPUT_CHARS],
        )
