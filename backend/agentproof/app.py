"""FastAPI entry point for the local AgentProof application."""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agentproof import __version__
from agentproof.challenges import ChallengeError, IndependentChallengeRunner
from agentproof.models import (
    AutomaticVerificationRequest,
    BaselineApprovalRequest,
    BaselineApprovalResponse,
    CapabilitiesResponse,
    HealthResponse,
    IndependentChallengeReport,
    IndependentChallengeRequest,
    ModelEvaluationRubric,
    ProjectInspection,
    ProjectInspectionRequest,
    VerificationReport,
    VerificationRequest,
)
from agentproof.projects import ProjectInputError, ProjectStore
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
project_store = ProjectStore()
challenge_runner = IndependentChallengeRunner(verifier)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentproof", version=__version__)


@app.get("/api/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        phase="2.5",
        status="baseline_manager",
        implemented=[
            "typed local API",
            "model evaluation rubric",
            "immutable pytest input snapshots",
            "disposable Git workspaces",
            "bounded baseline execution",
            "local evidence reports",
            "stable repository identities",
            "isolated immutable baseline histories",
            "automatic baseline-relative change discovery",
        ],
        planned=[
            "model bake-off",
            "invariant extraction",
            "adversarial-test generation",
        ],
    )


@app.get("/api/challenges/capabilities", response_model=CapabilitiesResponse)
def challenge_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        phase="3",
        status="model_challenges",
        implemented=[
            "single-request local model adapter",
            "structured invariant and pytest challenge generation",
            "generated-test safety validation",
            "deterministic baseline-versus-candidate challenge execution",
            "local model prompt, response, usage, and command trajectories",
        ],
        planned=[
            "model bake-off",
            "multi-language challenge adapters",
            "container-level execution isolation",
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


@app.post("/api/projects/inspect", response_model=ProjectInspection)
def inspect_project(request: ProjectInspectionRequest) -> ProjectInspection:
    """Identify a project, inspect baseline-relative changes, and audit its current state."""
    try:
        return project_store.inspect(request.repository_path, request.timeout_seconds)
    except ProjectInputError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.post(
    "/api/projects/baselines",
    response_model=BaselineApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_project_baseline(request: BaselineApprovalRequest) -> BaselineApprovalResponse:
    """Create an immutable baseline only after an explicit human approval request."""
    try:
        return project_store.approve_baseline(request)
    except ProjectInputError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.post(
    "/api/verifications/automatic",
    response_model=VerificationReport,
    status_code=status.HTTP_201_CREATED,
)
def create_automatic_verification(
    request: AutomaticVerificationRequest,
) -> VerificationReport:
    """Discover and verify changes against the correct approved project baseline."""
    try:
        return project_store.verify_automatic(request, verifier)
    except (ProjectInputError, VerificationInputError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.get("/api/verifications/{run_id}", response_model=VerificationReport)
def get_verification(run_id: str) -> VerificationReport:
    """Retrieve a local evidence report without re-running the repository."""
    try:
        return verifier.get_report(run_id)
    except VerificationInputError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@app.post(
    "/api/challenges",
    response_model=IndependentChallengeReport,
    status_code=status.HTTP_201_CREATED,
)
def create_independent_challenge(
    request: IndependentChallengeRequest,
) -> IndependentChallengeReport:
    """Ask one local model for a test, then let deterministic execution own the verdict."""
    try:
        return challenge_runner.run(request)
    except ChallengeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
