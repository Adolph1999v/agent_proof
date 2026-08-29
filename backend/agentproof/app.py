"""FastAPI entry point for the local AgentProof application."""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agentproof import __version__
from agentproof.models import (
    CapabilitiesResponse,
    HealthResponse,
    ModelEvaluationRubric,
    VerificationReport,
    VerificationRequest,
)
from agentproof.rubric import MODEL_CANDIDATES, MODEL_SCORE_CATEGORIES, MODEL_SCORE_TOTAL
from agentproof.verifier import DeterministicVerifier, VerificationInputError

app = FastAPI(
    title="AgentProof API",
    description="Independent, evidence-backed verification for AI-generated patches.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

verifier = DeterministicVerifier()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentproof", version=__version__)


@app.get("/api/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        phase=2,
        status="deterministic_verifier",
        implemented=[
            "typed local API",
            "model evaluation rubric",
            "immutable pytest input snapshots",
            "disposable Git workspaces",
            "bounded baseline execution",
            "local evidence reports",
        ],
        planned=[
            "model bake-off",
            "invariant extraction",
            "adversarial-test generation",
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


@app.post(
    "/api/verifications",
    response_model=VerificationReport,
    status_code=status.HTTP_201_CREATED,
)
def create_verification(request: VerificationRequest) -> VerificationReport:
    """Run the deterministic Phase 2 checks in an AgentProof-owned disposable clone."""
    try:
        return verifier.verify(request)
    except VerificationInputError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.get("/api/verifications/{run_id}", response_model=VerificationReport)
def get_verification(run_id: str) -> VerificationReport:
    """Retrieve a local evidence report without re-running the repository."""
    try:
        return verifier.get_report(run_id)
    except VerificationInputError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
