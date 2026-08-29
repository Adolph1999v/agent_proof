import asyncio

import httpx
from agentproof.app import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_health_reports_service_version() -> None:
    response = get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentproof",
        "version": "0.1.0",
    }


def test_capabilities_are_honest_about_phase_one_scope() -> None:
    response = get("/api/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == 1
    assert payload["status"] == "foundation"
    assert "patch and trace intake" in payload["planned"]


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
