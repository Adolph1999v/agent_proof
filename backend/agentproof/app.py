"""FastAPI entry point for the local AgentProof application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentproof import __version__
from agentproof.models import CapabilitiesResponse, HealthResponse, ModelEvaluationRubric
from agentproof.rubric import MODEL_CANDIDATES, MODEL_SCORE_CATEGORIES, MODEL_SCORE_TOTAL

app = FastAPI(
    title="AgentProof API",
    description="Independent, evidence-backed verification for AI-generated patches.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentproof", version=__version__)


@app.get("/api/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        phase=1,
        status="foundation",
        implemented=[
            "typed local API",
            "model evaluation rubric",
            "React working surface",
            "automated quality gates",
        ],
        planned=[
            "patch and trace intake",
            "immutable test snapshots",
            "disposable verification workspaces",
            "local model bake-off",
        ],
    )


@app.get("/api/model-evaluation/rubric", response_model=ModelEvaluationRubric)
def model_evaluation_rubric() -> ModelEvaluationRubric:
    return ModelEvaluationRubric(
        candidates=MODEL_CANDIDATES,
        categories=MODEL_SCORE_CATEGORIES,
        total_weight=MODEL_SCORE_TOTAL,
        correctness_is_gate=True,
    )
