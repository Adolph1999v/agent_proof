"""Typed API models for AgentProof's deterministic verification workflow."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ModelScoreCategory(BaseModel):
    key: str
    label: str
    weight: int = Field(ge=0, le=100)


class ModelEvaluationRubric(BaseModel):
    candidates: list[str]
    categories: list[ModelScoreCategory]
    total_weight: int
    correctness_is_gate: bool


class CapabilitiesResponse(BaseModel):
    phase: str
    status: Literal[
        "foundation",
        "deterministic_verifier",
        "baseline_manager",
        "model_challenges",
    ]
    implemented: list[str]
    planned: list[str]


class VerificationRequest(BaseModel):
    """The user-approved inputs for one local deterministic verification run."""

    repository_path: str = Field(min_length=1, max_length=4096)
    task: str = Field(min_length=1, max_length=20_000)
    patch: str = Field(min_length=1, max_length=1_000_000)
    trace: str | None = Field(default=None, max_length=200_000)
    timeout_seconds: int = Field(default=45, ge=1, le=120)

    @field_validator("repository_path", "task")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("patch")
    @classmethod
    def patch_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Patch must not be blank.")
        return value


class InputDigests(BaseModel):
    task_sha256: str
    patch_sha256: str
    trace_sha256: str | None = None


class ProtectedSnapshot(BaseModel):
    file_count: int
    digest: str
    files: list[str]


class CommandEvidence(BaseModel):
    command: list[str] = Field(default_factory=list)
    status: Literal["passed", "failed", "timed_out", "not_run"]
    exit_code: int | None = None
    duration_ms: int | None = None
    output_preview: str | None = None


class ChangedFile(BaseModel):
    path: str
    added_lines: int = Field(ge=0)
    deleted_lines: int = Field(ge=0)
    protected: bool


class ProjectChange(BaseModel):
    path: str
    status: Literal["added", "modified", "deleted", "renamed"]
    previous_path: str | None = None


class BaselineSummary(BaseModel):
    baseline_id: str
    repository_id: str
    created_at: datetime
    parent_baseline_id: str | None = None
    task: str
    file_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    manifest_digest: str
    source_commit: str | None = None
    evidence_run_id: str | None = None


class CurrentStateAudit(BaseModel):
    status: Literal["passed", "failed", "timed_out", "not_supported"]
    summary: str
    test_execution: CommandEvidence
    evidence_path: str


class ProjectInspectionRequest(BaseModel):
    repository_path: str = Field(min_length=1, max_length=4096)
    timeout_seconds: int = Field(default=45, ge=1, le=120)

    @field_validator("repository_path")
    @classmethod
    def repository_path_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Repository path must not be blank.")
        return value


class ProjectInspection(BaseModel):
    repository_id: str
    name: str
    current_path: str
    path_changed: bool
    identity_kind: Literal["git", "folder"]
    current_digest: str
    current_file_count: int = Field(ge=0)
    baseline_count: int = Field(ge=0)
    latest_baseline: BaselineSummary | None = None
    changes: list[ProjectChange]
    current_state_audit: CurrentStateAudit | None = None


class BaselineApprovalRequest(BaseModel):
    repository_path: str = Field(min_length=1, max_length=4096)
    expected_current_digest: str = Field(min_length=64, max_length=64)
    task: str = Field(min_length=1, max_length=20_000)
    evidence_run_id: str | None = Field(default=None, max_length=128)

    @field_validator("repository_path", "task")
    @classmethod
    def approval_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class BaselineApprovalResponse(BaseModel):
    baseline: BaselineSummary
    project: ProjectInspection


class AutomaticVerificationRequest(BaseModel):
    repository_path: str = Field(min_length=1, max_length=4096)
    task: str = Field(min_length=1, max_length=20_000)
    trace: str | None = Field(default=None, max_length=200_000)
    timeout_seconds: int = Field(default=45, ge=1, le=120)

    @field_validator("repository_path", "task")
    @classmethod
    def automatic_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class VerificationReport(BaseModel):
    """Reproducible Phase 2 evidence, not an LLM confidence score."""

    run_id: str
    created_at: datetime
    verdict: Literal["UNSAFE", "INCONCLUSIVE"]
    summary: str
    execution_mode: Literal["portable_local"]
    repository: str
    source_commit: str
    repository_id: str | None = None
    baseline_id: str | None = None
    baseline_manifest_digest: str | None = None
    change_source: Literal["manual_patch", "approved_baseline"] = "manual_patch"
    input_digests: InputDigests
    patch_normalized: bool = False
    protected_snapshot_before: ProtectedSnapshot
    protected_snapshot_after: ProtectedSnapshot
    protected_inputs_changed: list[str]
    changed_files: list[ChangedFile]
    patch_check: CommandEvidence
    test_execution: CommandEvidence
    evidence_path: str


class IndependentChallengeRequest(BaseModel):
    run_id: str = Field(pattern=r"^run-\d{8}T\d{6}Z-[0-9a-f]{8}$")
    task: str = Field(min_length=1, max_length=20_000)
    model_url: str = Field(min_length=1, max_length=2048)
    model_name: str = Field(min_length=1, max_length=512)
    model_timeout_seconds: int = Field(default=300, ge=30, le=600)
    test_timeout_seconds: int = Field(default=45, ge=1, le=120)

    @field_validator("task", "model_url", "model_name")
    @classmethod
    def challenge_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class ChallengeProposalEvidence(BaseModel):
    behavior_mode: Literal["change", "preserve"]
    summary: str
    invariants: list[str]
    test_sha256: str
    test_path: str


class ModelRunEvidence(BaseModel):
    provider: str
    model: str
    prompt_sha256: str
    response_sha256: str
    duration_ms: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class IndependentChallengeReport(BaseModel):
    challenge_id: str
    created_at: datetime
    source_run_id: str
    verdict: Literal["VERIFIED", "UNSAFE", "INCONCLUSIVE"]
    summary: str
    proposal: ChallengeProposalEvidence
    model: ModelRunEvidence
    baseline_execution: CommandEvidence
    candidate_execution: CommandEvidence
    evidence_path: str
    trajectory_path: str


class DirectoryBrowseRequest(BaseModel):
    """Request body for browsing a directory."""

    path: str | None = Field(default=None, max_length=4096)


class DirectoryEntry(BaseModel):
    """A single child directory entry."""

    name: str
    path: str


class DirectoryBrowseResponse(BaseModel):
    """Response with the current directory listing."""

    current_path: str
    parent_path: str | None
    directories: list[DirectoryEntry]
