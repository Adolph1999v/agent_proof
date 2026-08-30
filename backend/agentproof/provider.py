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
        max_tokens: int = 2048,
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
        elif normalized.endswith("/v1"):
            self.endpoint = f"{normalized}/chat/completions"
        else:
            self.endpoint = f"{normalized}/v1/chat/completions"
        self.model = model.strip()
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    @property
    def label(self) -> str:
        return f"openai-compatible:{self.model}"

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
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "model": self.model,
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
            content = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
        except httpx.HTTPStatusError as error:
            detail = error.response.text.strip()[:500]
            raise ProviderError(
                f"The local model rejected the request with HTTP {error.response.status_code}: "
                f"{detail or 'no error detail returned'}"
            ) from error
        except (
            AttributeError,
            httpx.RequestError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as error:
            raise ProviderError(
                "The local model did not complete the challenge request. Confirm that the "
                "selected model is loaded and its local server is running."
            ) from error
        finally:
            _MODEL_REQUEST_LOCK.release()

        if not isinstance(content, str) or not content.strip():
            raise ProviderError("The local model returned an empty challenge response.")

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
            extra_usage=extra_usage,
        )
