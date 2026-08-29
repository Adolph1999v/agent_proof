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
    phase: int
    status: Literal["foundation", "deterministic_verifier"]
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


class VerificationReport(BaseModel):
    """Reproducible Phase 2 evidence, not an LLM confidence score."""

    run_id: str
    created_at: datetime
    verdict: Literal["UNSAFE", "INCONCLUSIVE"]
    summary: str
    execution_mode: Literal["portable_local"]
    repository: str
    source_commit: str
    input_digests: InputDigests
    patch_normalized: bool = False
    protected_snapshot_before: ProtectedSnapshot
    protected_snapshot_after: ProtectedSnapshot
    protected_inputs_changed: list[str]
    changed_files: list[ChangedFile]
    patch_check: CommandEvidence
    test_execution: CommandEvidence
    evidence_path: str
