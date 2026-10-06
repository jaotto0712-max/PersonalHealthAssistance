"""Streaming client for a local Ollama server (/api/chat, /api/tags)."""

import json
from collections.abc import AsyncIterator

import httpx

from pha.llm.base import (
    ChatMessage,
    GenerationOptions,
    GenerationStats,
    LlmError,
    LlmHealth,
    LlmUnavailable,
    ModelMissing,
)

START_HINT = "Start Ollama with `ollama serve` (or open the Ollama app), then try again."


def _missing_hint(model: str) -> str:
    return (
        f'The model "{model}" is not installed in Ollama. Create it from models/Modelfile.* '
        "(see README) or set PHA_MODEL to an installed model."
    )


class OllamaBackend:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,  # tests inject a mock transport
    ):
        self.model = model
        # Generous read timeout: the first token can take a while when the model is loading.
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_s, connect=5.0), transport=transport
        )

    async def stream(
        self, messages: list[ChatMessage], options: GenerationOptions, stats: GenerationStats
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "num_ctx": options.num_ctx,
                "num_predict": options.num_predict,
                "temperature": options.temperature,
            },
        }
        if options.seed is not None:
            payload["options"]["seed"] = options.seed
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code == 404:
                    raise ModelMissing(_missing_hint(self.model))
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode(errors="replace")
                    raise LlmError(f"Ollama returned HTTP {resp.status_code}: {body[:200]}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if error := chunk.get("error"):
                        raise LlmError(f"Ollama error: {error}")
                    if text := chunk.get("message", {}).get("content"):
                        yield text
                    if chunk.get("done"):
                        stats.prompt_tokens = chunk.get("prompt_eval_count")
                        stats.completion_tokens = chunk.get("eval_count")
                        if (dur := chunk.get("eval_duration")) and stats.completion_tokens:
                            stats.extra["tokens_per_s"] = stats.completion_tokens / (dur / 1e9)
                        return
        except httpx.ConnectError as e:
            raise LlmUnavailable(f"Cannot reach Ollama. {START_HINT}") from e
        except httpx.TimeoutException as e:
            raise LlmError("The model took too long to respond.") from e

    async def health(self) -> LlmHealth:
        try:
            resp = await self._client.get("/api/tags", timeout=3.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            return LlmHealth("unavailable", self.model, START_HINT)
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        wanted = {self.model, f"{self.model}:latest"}
        if names & wanted:
            return LlmHealth("ok", self.model)
        return LlmHealth("model_missing", self.model, _missing_hint(self.model))

    async def aclose(self) -> None:
        await self._client.aclose()
