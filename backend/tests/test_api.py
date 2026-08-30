import asyncio
import importlib
import subprocess
from pathlib import Path

import httpx
import pytest
from agentproof.app import app
from agentproof.projects import ProjectStore
from agentproof.verifier import DeterministicVerifier


def request(method: str, path: str, payload: dict[str, object] | None = None) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(request())


def get(path: str) -> httpx.Response:
    return request("GET", path)


def initialise_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "api-repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "service.py").write_text(
        "def value() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (repository / "tests" / "test_service.py").write_text(
        "from service import value\n\n\ndef test_value() -> None:\n    assert value() == 1\n",
        encoding="utf-8",
    )
    for arguments in (
        ("init", "--quiet"),
        ("add", "."),
        (
            "-c",
            "user.name=AgentProof Tests",
            "-c",
            "user.email=tests@agentproof.local",
            "commit",
            "--quiet",
            "-m",
            "Initial fixture",
        ),
    ):
        subprocess.run(["git", "-C", str(repository), *arguments], check=True)
    return repository


def test_health_reports_service_version() -> None:
    response = get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentproof",
        "version": "0.2.0",
    }


def test_capabilities_are_honest_about_phase_two_scope() -> None:
    response = get("/api/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "2.5"
    assert payload["status"] == "baseline_manager"
    assert "immutable pytest input snapshots" in payload["implemented"]
    assert "stable repository identities" in payload["implemented"]


def test_model_rubric_is_complete_and_weighted_to_100() -> None:
    response = get("/api/model-evaluation/rubric")

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"] == [
        "Qwen3.6 27B Q6",
        "Qwen3-Coder 30B",
        "Qwen2.5-Coder 7B",
    ]
    assert sum(category["weight"] for category in payload["categories"]) == 100
    assert payload["total_weight"] == 100
    assert payload["correctness_is_gate"] is True


def test_verification_api_creates_and_retrieves_local_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("agentproof.app")
    monkeypatch.setattr(module, "verifier", DeterministicVerifier(tmp_path / "artifacts" / "runs"))
    repository = initialise_repository(tmp_path)
    patch = """diff --git a/service.py b/service.py
index 1111111..2222222 100644
--- a/service.py
+++ b/service.py
@@ -1,2 +1,3 @@
+\"\"\"A tiny service.\"\"\"
 def value() -> int:
     return 1
"""

    response = request(
        "POST",
        "/api/verifications",
        {
            "repository_path": str(repository),
            "task": "Document the service without changing its behavior.",
            "patch": patch,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["verdict"] == "INCONCLUSIVE"
    assert payload["test_execution"]["status"] == "passed"

    retrieved = get(f"/api/verifications/{payload['run_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["run_id"] == payload["run_id"]


def test_project_api_inspects_and_approves_an_isolated_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("agentproof.app")
    monkeypatch.setattr(
        module,
        "project_store",
        ProjectStore(tmp_path / "state" / "projects", tmp_path / "state" / "audits"),
    )
    repository = initialise_repository(tmp_path)

    inspected = request(
        "POST",
        "/api/projects/inspect",
        {"repository_path": str(repository)},
    )

    assert inspected.status_code == 200
    project = inspected.json()
    assert project["baseline_count"] == 0
    assert project["current_state_audit"]["status"] == "passed"

    approved = request(
        "POST",
        "/api/projects/baselines",
        {
            "repository_path": str(repository),
            "expected_current_digest": project["current_digest"],
            "task": "Approve the initial state.",
        },
    )

    assert approved.status_code == 201
    assert approved.json()["project"]["baseline_count"] == 1
    assert approved.json()["baseline"]["repository_id"] == project["repository_id"]
