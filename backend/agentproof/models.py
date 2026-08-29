"""Typed API models for the AgentProof foundation."""

from typing import Literal

from pydantic import BaseModel, Field


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
    status: Literal["foundation"]
    implemented: list[str]
    planned: list[str]
