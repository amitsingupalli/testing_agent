"""Direct LLM backends (Anthropic Messages API, OpenAI Chat Completions)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from testing_agent.generate.backends import Backend, GenerationError
from testing_agent.generate.models import GenerationTarget
from testing_agent.generate.prompts import build_generation_prompt, extract_code_block

_SYSTEM_PROMPT = (
    "You are a test engineer. You output only the complete content of the requested "
    "test file inside a single code block. No explanations, no prose."
)

_MAX_COMPLETION_TOKENS = 4000
_HTTP_TIMEOUT_SECONDS = 120.0


class AnthropicBackend(Backend):
    """Calls the Anthropic Messages API with ANTHROPIC_API_KEY."""

    id = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model or os.environ.get("TESTING_AGENT_ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        root: Path,
        target: GenerationTarget,
        framework: str,
        timeout_seconds: int,
        failure_feedback: str | None = None,
    ) -> str:
        if not self._api_key:
            raise GenerationError("ANTHROPIC_API_KEY is not set")
        prompt = build_generation_prompt(root, target, framework, failure_feedback)
        return self._request(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload={
                "model": self._model,
                "max_tokens": _MAX_COMPLETION_TOKENS,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            response_text=lambda data: "".join(
                block.get("text", "") for block in data.get("content", [])
            ),
        )

    def _request(self, url, headers, payload, response_text) -> str:
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as error:
            raise GenerationError(f"anthropic request failed: {error}") from error
        if response.status_code != 200:
            raise GenerationError(
                f"anthropic API returned {response.status_code}: {response.text[:300]}"
            )
        text = response_text(response.json())
        code = extract_code_block(text)
        if not code.strip():
            raise GenerationError("anthropic response contained no code")
        return code


class OpenAIBackend(Backend):
    """Calls the OpenAI Chat Completions API with OPENAI_API_KEY."""

    id = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or os.environ.get("TESTING_AGENT_OPENAI_MODEL", "gpt-4o-mini")

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        root: Path,
        target: GenerationTarget,
        framework: str,
        timeout_seconds: int,
        failure_feedback: str | None = None,
    ) -> str:
        if not self._api_key:
            raise GenerationError("OPENAI_API_KEY is not set")
        prompt = build_generation_prompt(root, target, framework, failure_feedback)
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as error:
            raise GenerationError(f"openai request failed: {error}") from error
        if response.status_code != 200:
            raise GenerationError(
                f"openai API returned {response.status_code}: {response.text[:300]}"
            )
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as error:
            raise GenerationError(f"unexpected openai response shape: {error}") from error
        code = extract_code_block(text)
        if not code.strip():
            raise GenerationError("openai response contained no code")
        return code
