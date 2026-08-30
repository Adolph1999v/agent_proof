import asyncio

import httpx
from agentproof.app import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_phase_three_capabilities_describe_the_model_boundary() -> None:
    response = get("/api/challenges/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "3"
    assert payload["status"] == "model_challenges"
    assert "single-request local model adapter" in payload["implemented"]
    assert "generated-test safety validation" in payload["implemented"]
