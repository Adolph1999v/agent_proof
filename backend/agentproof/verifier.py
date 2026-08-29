"""Deterministic, local-only verification for user-approved Git repositories.

This module deliberately does not ask a model whether a patch is correct. It creates an
AgentProof-owned disposable clone, freezes protected test inputs, applies the candidate patch
only in that clone, and runs a fixed pytest command when that adapter is available.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from agentproof.models import (
    ChangedFile,
    CommandEvidence,
    InputDigests,
    ProtectedSnapshot,
    VerificationReport,
    VerificationRequest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "runs"
MAX_OUTPUT_CHARS = 12_000
GIT_TIMEOUT_SECONDS = 30
PYTEST_COMMAND = [sys.executable, "-m", "pytest", "-q"]
PROTECTED_CONFIG_NAMES = {"pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml"}


class VerificationInputError(ValueError):
    """Raised when a request cannot be evaluated safely or reproducibly."""


@dataclass(frozen=True)
class _ProcessResult:
    command: list[str]
    returncode: int | None
    duration_ms: int
    output: str
    timed_out: bool = False

    def as_evidence(self) -> CommandEvidence:
        if self.timed_out:
            status = "timed_out"
        elif self.returncode == 0:
            status = "passed"
        else:
            status = "failed"
        return CommandEvidence(
            command=self.command,
            status=status,
            exit_code=self.returncode,
            duration_ms=self.duration_ms,
            output_preview=_preview(self.output),
        )


def _preview(value: str) -> str:
    """Keep API and evidence files readable without retaining unlimited command output."""
    if len(value) <= MAX_OUTPUT_CHARS:
        return value
    return f"{value[:MAX_OUTPUT_CHARS]}\n… output truncated by AgentProof …"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_protected_path(relative_path: Path) -> bool:
    """Return whether a file is an existing test or test-discovery configuration input."""
    normalized = relative_path.as_posix().lower()
    name = relative_path.name.lower()
    parts = {part.lower() for part in relative_path.parts}

    if name == "conftest.py" or name in PROTECTED_CONFIG_NAMES:
        return True
    if {"test", "tests", "__tests__"} & parts:
        return True
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
        or normalized.startswith("tests/")
    )


def _snapshot_protected_inputs(workspace: Path) -> tuple[ProtectedSnapshot, dict[str, str]]:
    """Hash protected files so a patch cannot weaken the baseline test evidence."""
    hashes: dict[str, str] = {}
    ignored_parts = {".git", ".venv", "venv", "node_modules", "__pycache__"}

    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace)
        if ignored_parts & set(relative.parts):
            continue
        if _is_protected_path(relative):
            hashes[relative.as_posix()] = _sha256_file(path)

    digest_input = "".join(f"{path}\0{digest}\n" for path, digest in sorted(hashes.items()))
    snapshot = ProtectedSnapshot(
        file_count=len(hashes),
        digest=_sha256_text(digest_input),
        files=sorted(hashes),
    )
    return snapshot, hashes


def _changed_protected_inputs(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Block changed baseline inputs and newly introduced pytest configuration, not new tests."""
    changed = {path for path, digest in before.items() if after.get(path) != digest}
    changed.update(
        path
        for path in set(after) - set(before)
        if Path(path).name.lower() in PROTECTED_CONFIG_NAMES
        or Path(path).name.lower() == "conftest.py"
    )
    return sorted(changed)


def _uses_pytest(workspace: Path, snapshot: ProtectedSnapshot) -> bool:
    """Detect the intentionally narrow Phase 2 pytest adapter."""
    if any(path.endswith(".py") for path in snapshot.files):
        return True
    return any(
        (workspace / configuration).exists()
        for configuration in ("pytest.ini", "pyproject.toml", "tox.ini")
    )


class DeterministicVerifier:
    """Runs a reproducible, non-LLM patch inspection in a disposable local clone."""

    def __init__(self, artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT) -> None:
        self.artifacts_root = artifacts_root

    def verify(self, request: VerificationRequest) -> VerificationReport:
        repository = self._resolve_repository(Path(request.repository_path))
        source_commit = self._read_source_commit(repository)
        digests = InputDigests(
            task_sha256=_sha256_text(request.task),
            patch_sha256=_sha256_text(request.patch),
            trace_sha256=_sha256_text(request.trace) if request.trace else None,
        )
        run_id = self._new_run_id()
        run_directory = self.artifacts_root / run_id
        workspace = run_directory / "workspace"
        run_directory.mkdir(parents=True, exist_ok=False)
        patch_path = run_directory / "candidate.patch"
        patch_path.write_text(request.patch, encoding="utf-8")
        empty_snapshot = ProtectedSnapshot(
            file_count=0,
            digest=_sha256_text(""),
            files=[],
        )

        clone_result = self._run(
            ["git", "clone", "--quiet", "--no-local", str(repository), str(workspace)],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if clone_result.returncode != 0 or clone_result.timed_out:
            return self._write_report(
                self._report(
                    run_id=run_id,
                    request=request,
                    repository=repository,
                    source_commit=source_commit,
                    digests=digests,
                    snapshot_before=empty_snapshot,
                    snapshot_after=empty_snapshot,
                    verdict="INCONCLUSIVE",
                    summary="AgentProof could not create its disposable workspace.",
                    patch_check=CommandEvidence(
                        status="not_run",
                        output_preview=(
                            "Patch was not inspected because the workspace clone failed."
                        ),
                    ),
                    test_execution=CommandEvidence(
                        status="not_run",
                        output_preview="Tests were not run because the workspace clone failed.",
                    ),
                ),
                run_directory,
            )

        snapshot_before, before_hashes = _snapshot_protected_inputs(workspace)
        patch_check = self._run(
            [
                "git",
                "-C",
                str(workspace),
                "apply",
                "--check",
                "--recount",
                "--whitespace=nowarn",
                str(patch_path),
            ],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if patch_check.returncode != 0 or patch_check.timed_out:
            return self._write_report(
                self._report(
                    run_id=run_id,
                    request=request,
                    repository=repository,
                    source_commit=source_commit,
                    digests=digests,
                    snapshot_before=snapshot_before,
                    snapshot_after=snapshot_before,
                    verdict="UNSAFE",
                    summary=(
                        "The candidate patch could not be applied cleanly in a disposable "
                        "workspace."
                    ),
                    patch_check=patch_check.as_evidence(),
                    test_execution=CommandEvidence(
                        status="not_run",
                        output_preview="Tests were not run because the patch check failed.",
                    ),
                ),
                run_directory,
            )

        patch_apply = self._run(
            [
                "git",
                "-C",
                str(workspace),
                "apply",
                "--recount",
                "--whitespace=nowarn",
                str(patch_path),
            ],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if patch_apply.returncode != 0 or patch_apply.timed_out:
            return self._write_report(
                self._report(
                    run_id=run_id,
                    request=request,
                    repository=repository,
                    source_commit=source_commit,
                    digests=digests,
                    snapshot_before=snapshot_before,
                    snapshot_after=snapshot_before,
                    verdict="UNSAFE",
                    summary="The candidate patch passed preflight but failed during application.",
                    patch_check=patch_apply.as_evidence(),
                    test_execution=CommandEvidence(
                        status="not_run",
                        output_preview="Tests were not run because the patch could not be applied.",
                    ),
                ),
                run_directory,
            )

        snapshot_after, after_hashes = _snapshot_protected_inputs(workspace)
        protected_inputs_changed = _changed_protected_inputs(before_hashes, after_hashes)
        changed_files = self._changed_files(workspace, before_hashes)

        if protected_inputs_changed:
            return self._write_report(
                self._report(
                    run_id=run_id,
                    request=request,
                    repository=repository,
                    source_commit=source_commit,
                    digests=digests,
                    snapshot_before=snapshot_before,
                    snapshot_after=snapshot_after,
                    verdict="UNSAFE",
                    summary="The patch modifies protected baseline tests or test configuration.",
                    protected_inputs_changed=protected_inputs_changed,
                    changed_files=changed_files,
                    patch_check=patch_check.as_evidence(),
                    test_execution=CommandEvidence(
                        status="not_run",
                        output_preview="Tests were not run after protected inputs changed.",
                    ),
                ),
                run_directory,
            )

        if not _uses_pytest(workspace, snapshot_before):
            return self._write_report(
                self._report(
                    run_id=run_id,
                    request=request,
                    repository=repository,
                    source_commit=source_commit,
                    digests=digests,
                    snapshot_before=snapshot_before,
                    snapshot_after=snapshot_after,
                    verdict="INCONCLUSIVE",
                    summary="No supported pytest baseline was found in this repository.",
                    changed_files=changed_files,
                    patch_check=patch_check.as_evidence(),
                    test_execution=CommandEvidence(
                        status="not_run",
                        output_preview="Phase 2 currently supports the fixed pytest adapter only.",
                    ),
                ),
                run_directory,
            )

        test_result = self._run(
            PYTEST_COMMAND,
            cwd=workspace,
            timeout_seconds=request.timeout_seconds,
        )
        if test_result.timed_out:
            verdict = "INCONCLUSIVE"
            summary = "The baseline test command timed out in the disposable workspace."
        elif test_result.returncode != 0:
            verdict = "UNSAFE"
            summary = "The immutable baseline test suite failed after the patch was applied."
        else:
            verdict = "INCONCLUSIVE"
            summary = (
                "Baseline evidence passed, but independent challenge tests have not yet been "
                "performed."
            )

        return self._write_report(
            self._report(
                run_id=run_id,
                request=request,
                repository=repository,
                source_commit=source_commit,
                digests=digests,
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
                verdict=verdict,
                summary=summary,
                changed_files=changed_files,
                patch_check=patch_check.as_evidence(),
                test_execution=test_result.as_evidence(),
            ),
            run_directory,
        )

    def get_report(self, run_id: str) -> VerificationReport:
        """Load previously produced local evidence by its opaque run identifier."""
        if not re.fullmatch(r"run-\d{8}T\d{6}Z-[0-9a-f]{8}", run_id):
            raise VerificationInputError("Invalid verification run identifier.")
        evidence_path = self.artifacts_root / run_id / "report.json"
        if not evidence_path.is_file():
            raise VerificationInputError("Verification report was not found.")
        return VerificationReport.model_validate_json(evidence_path.read_text(encoding="utf-8"))

    def _resolve_repository(self, requested_path: Path) -> Path:
        path = requested_path.expanduser().resolve()
        if not path.is_dir():
            raise VerificationInputError("Repository path must be an existing directory.")

        root_result = self._run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if root_result.returncode != 0 or root_result.timed_out:
            raise VerificationInputError(
                "Repository path must be inside a readable Git working tree."
            )

        repository = Path(root_result.output.strip()).resolve()
        dirty_result = self._run(
            ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if dirty_result.returncode != 0:
            raise VerificationInputError(
                "AgentProof could not inspect the repository working tree."
            )
        if dirty_result.output.strip():
            raise VerificationInputError(
                "Repository has tracked changes. Commit or stash them before deterministic "
                "verification."
            )
        return repository

    def _read_source_commit(self, repository: Path) -> str:
        result = self._run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if result.returncode != 0 or result.timed_out:
            raise VerificationInputError("Repository must have a readable HEAD commit.")
        return result.output.strip()

    def _changed_files(
        self,
        workspace: Path,
        protected_before: dict[str, str],
    ) -> list[ChangedFile]:
        result = self._run(
            ["git", "-C", str(workspace), "diff", "--numstat", "HEAD"],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
        if result.returncode != 0 or result.timed_out:
            return []

        files: list[ChangedFile] = []
        for line in result.output.splitlines():
            parts = line.split("\t", maxsplit=2)
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            files.append(
                ChangedFile(
                    path=path,
                    added_lines=int(added) if added.isdigit() else 0,
                    deleted_lines=int(deleted) if deleted.isdigit() else 0,
                    protected=path in protected_before,
                )
            )
        return files

    def _report(
        self,
        *,
        run_id: str,
        request: VerificationRequest,
        repository: Path,
        source_commit: str,
        digests: InputDigests,
        snapshot_before: ProtectedSnapshot,
        snapshot_after: ProtectedSnapshot,
        verdict: Literal["UNSAFE", "INCONCLUSIVE"],
        summary: str,
        patch_check: CommandEvidence,
        test_execution: CommandEvidence,
        protected_inputs_changed: list[str] | None = None,
        changed_files: list[ChangedFile] | None = None,
    ) -> VerificationReport:
        return VerificationReport(
            run_id=run_id,
            created_at=datetime.now(UTC),
            verdict=verdict,
            summary=summary,
            execution_mode="portable_local",
            repository=str(repository),
            source_commit=source_commit,
            input_digests=digests,
            protected_snapshot_before=snapshot_before,
            protected_snapshot_after=snapshot_after,
            protected_inputs_changed=protected_inputs_changed or [],
            changed_files=changed_files or [],
            patch_check=patch_check,
            test_execution=test_execution,
            evidence_path=f"artifacts/runs/{run_id}/report.json",
        )

    def _write_report(self, report: VerificationReport, run_directory: Path) -> VerificationReport:
        report_path = run_directory / "report.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report

    @staticmethod
    def _new_run_id() -> str:
        return f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _run(
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: int = GIT_TIMEOUT_SECONDS,
    ) -> _ProcessResult:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                env=environment,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return _ProcessResult(
                command=command,
                returncode=None,
                duration_ms=round((time.monotonic() - started) * 1000),
                output=f"{output}\nAgentProof timed out after {timeout_seconds} seconds.",
                timed_out=True,
            )
        except OSError as error:
            return _ProcessResult(
                command=command,
                returncode=127,
                duration_ms=round((time.monotonic() - started) * 1000),
                output=str(error),
            )

        return _ProcessResult(
            command=command,
            returncode=completed.returncode,
            duration_ms=round((time.monotonic() - started) * 1000),
            output=completed.stdout or "",
        )
