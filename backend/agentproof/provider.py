"""Local-only, OpenAI-compatible model access with single-request admission."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

import httpx

_MODEL_REQUEST_LOCK = threading.Lock()
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_AUTO_MODEL = "auto"
CHALLENGE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "agentproof_challenge",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "behavior_mode": {"type": "string", "enum": ["change", "preserve"]},
                "summary": {"type": "string"},
                "invariants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                },
                "test_code": {"type": "string"},
            },
            "required": ["behavior_mode", "summary", "invariants", "test_code"],
            "additionalProperties": False,
        },
    },
}


class ProviderError(RuntimeError):
    """Raised when a local model request cannot be completed safely."""


@dataclass(frozen=True)
class ModelCompletion:
    content: str
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None
    reasoning_content: str | None = None
    extra_usage: dict[str, int] = field(default_factory=dict)


class ChallengeProvider(Protocol):
    @property
    def label(self) -> str: ...

    def complete(self, system_prompt: str, user_prompt: str) -> ModelCompletion: ...


class OpenAICompatibleProvider:
    """Call LM Studio or Ollama without allowing remote repository disclosure."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout_seconds: int = 300,
        max_tokens: int = 512,
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in _LOOPBACK_HOSTS
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ProviderError(
                "AgentProof accepts only plain HTTP model endpoints on this computer."
            )
        if not model.strip():
            raise ProviderError("A local model name is required.")

        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            self.endpoint = normalized
            self.models_endpoint = normalized.removesuffix("/chat/completions") + "/models"
        elif normalized.endswith("/v1"):
            self.endpoint = f"{normalized}/chat/completions"
            self.models_endpoint = f"{normalized}/models"
        else:
            self.endpoint = f"{normalized}/v1/chat/completions"
            self.models_endpoint = f"{normalized}/v1/models"
        self.model = model.strip()
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    @property
    def label(self) -> str:
        return f"openai-compatible:{self.model}"

    def _resolve_model(self, client: httpx.Client, headers: dict[str, str]) -> str:
        if self.model.casefold() != _AUTO_MODEL:
            return self.model

        response = client.get(self.models_endpoint, headers=headers, timeout=5)
        response.raise_for_status()
        payload = response.json()
        model_ids = [
            item.get("id", "").strip()
            for item in payload.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        generation_models = [
            model_id
            for model_id in model_ids
            if model_id and not any(term in model_id.casefold() for term in ("embed", "rerank"))
        ]
        if len(generation_models) == 1:
            self.model = generation_models[0]
            return self.model
        if not generation_models:
            raise ProviderError(
                "No loaded text-generation model was found. Load one model in LM Studio or Ollama."
            )
        loaded = ", ".join(generation_models)
        raise ProviderError(
            "More than one text-generation model is loaded. Keep one model loaded or enter one "
            f"of these exact IDs: {loaded}"
        )

    def complete(self, system_prompt: str, user_prompt: str) -> ModelCompletion:
        if not _MODEL_REQUEST_LOCK.acquire(blocking=False):
            raise ProviderError(
                "Another local-model request is already running. AgentProof runs one model "
                "at a time to protect system memory."
            )

        started = time.monotonic()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                model = self._resolve_model(client, headers)
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0,
                        "seed": 42,
                        "max_tokens": self.max_tokens,
                        "response_format": CHALLENGE_RESPONSE_FORMAT,
                        "stream": False,
                    },
                )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            reasoning_content = message.get("reasoning_content") or None
            finish_reason = choice.get("finish_reason") or None
            usage = payload.get("usage") or {}
        except httpx.HTTPStatusError as error:
            detail = error.response.text.strip()[:500]
            raise ProviderError(
                f"The local model rejected the request with HTTP {error.response.status_code}: "
                f"{detail or 'no error detail returned'}"
            ) from error
        except httpx.TimeoutException as error:
            raise ProviderError(
                "The local model did not return a challenge within "
                f"{self.timeout_seconds} seconds."
            ) from error
        except (
            AttributeError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            httpx.RequestError,
        ) as error:
            raise ProviderError(
                "The local model did not complete the challenge request. Confirm that the "
                "selected model is loaded and its local server is running."
            ) from error
        finally:
            _MODEL_REQUEST_LOCK.release()

        if not isinstance(content, str):
            raise ProviderError("The local model returned an unsupported challenge response.")

        known_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
        extra_usage = {
            key: int(value)
            for key, value in usage.items()
            if key not in known_usage and isinstance(value, int)
        }
        return ModelCompletion(
            content=content,
            duration_ms=round((time.monotonic() - started) * 1000),
            prompt_tokens=known_usage["prompt_tokens"],
            completion_tokens=known_usage["completion_tokens"],
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            reasoning_content=(
                str(reasoning_content) if reasoning_content is not None else None
            ),
            extra_usage=extra_usage,
        )
