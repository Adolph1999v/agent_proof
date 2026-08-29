"""Pinned model-selection rubric shared by the API and evaluation tooling."""

from agentproof.models import ModelScoreCategory

MODEL_CANDIDATES = [
    "Qwen3.6 27B Q6",
    "Qwen3-Coder 30B",
    "Qwen2.5-Coder 7B",
]

MODEL_SCORE_CATEGORIES = [
    ModelScoreCategory(
        key="unsafe_patch_detection",
        label="Correctly catches unsafe patches",
        weight=40,
    ),
    ModelScoreCategory(
        key="correct_patch_acceptance",
        label="Does not block correct patches",
        weight=20,
    ),
    ModelScoreCategory(
        key="executable_tests",
        label="Produces relevant, executable tests",
        weight=20,
    ),
    ModelScoreCategory(key="execution_time", label="Execution time", weight=10),
    ModelScoreCategory(
        key="resource_efficiency",
        label="Tokens and memory usage",
        weight=10,
    ),
]

MODEL_SCORE_TOTAL = sum(category.weight for category in MODEL_SCORE_CATEGORIES)

if MODEL_SCORE_TOTAL != 100:
    raise RuntimeError("Model evaluation weights must sum to 100")
