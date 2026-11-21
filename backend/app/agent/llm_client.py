"""Multi-provider async LLM state extractor (OpenAI / Gemini / Ollama) with 2.5s timeout + 1 retry."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.prompts.system_prompt import MASTER_SYSTEM_PROMPT, build_llm_user_prompt
from app.schemas.context import LLMExtractionOutput, UserContext


class LLMFallbackTriggered(Exception):
    """Raised when an external LLM times out (> 2.5s) or fails schema validation after 1 retry."""


JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    match = JSON_FENCE_RE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output root must be a JSON object")
    return parsed


class LLMClient:
    """Async structured-JSON extractor supporting OpenAI, Gemini, and Ollama."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def extract_turn(
        self,
        *,
        provider: str,
        current_context: UserContext,
        chat_history: list[dict[str, str]],
        user_message: str,
    ) -> LLMExtractionOutput:
        user_prompt = build_llm_user_prompt(
            current_context=current_context,
            chat_history=chat_history,
            user_message=user_message,
        )
        last_error: Exception | None = None

        # Spec 07: timeout (>2.5s) or schema validation failure -> 1 retry -> deterministic fallback
        for _attempt in range(2):
            try:
                raw_text = await self._call_provider(provider=provider, user_prompt=user_prompt)
                payload = _extract_json_object(raw_text)
                return LLMExtractionOutput.model_validate(payload)
            except Exception as exc:
                last_error = exc
                continue

        raise LLMFallbackTriggered(f"LLM extraction failed after retry: {last_error}")

    async def _call_provider(self, *, provider: str, user_prompt: str) -> str:
        timeout = httpx.Timeout(self.settings.llm_timeout_secs)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "openrouter":
                headers = {
                    "Authorization": f"Bearer {self.settings.openrouter_api_key.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": self.settings.openrouter_site_url,
                    "X-Title": self.settings.openrouter_app_name,
                }
                body: dict[str, Any] = {
                    "model": self.settings.openrouter_model,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                resp = await client.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=body,
                )
                # Some OpenRouter models reject response_format; retry once without it
                if resp.status_code == 400:
                    body.pop("response_format", None)
                    resp = await client.post(
                        f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            if provider == "openai":
                resp = await client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key.strip()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openai_model,
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            if provider == "gemini":
                model = self.settings.gemini_model
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    f"?key={self.settings.gemini_api_key.strip()}"
                )
                resp = await client.post(
                    url,
                    json={
                        "systemInstruction": {"parts": [{"text": MASTER_SYSTEM_PROMPT}]},
                        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

            if provider == "ollama":
                resp = await client.post(
                    f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                    json={
                        "model": self.settings.ollama_model,
                        "stream": False,
                        "format": "json",
                        "messages": [
                            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]

        raise ValueError(f"Unsupported external LLM provider: {provider}")
