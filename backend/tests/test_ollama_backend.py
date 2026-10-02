import json

import httpx
import pytest

from pha.llm.base import (
    ChatMessage,
    GenerationOptions,
    GenerationStats,
    LlmUnavailable,
    ModelMissing,
)
from pha.llm.ollama import OllamaBackend

OPTIONS = GenerationOptions(num_ctx=4096, num_predict=768, temperature=0.2)
MESSAGES = [ChatMessage("system", "s"), ChatMessage("user", "hi")]


def backend(handler, model="phi3-medquad") -> OllamaBackend:
    return OllamaBackend(
        "http://127.0.0.1:11434", model, 30, transport=httpx.MockTransport(handler)
    )


async def test_streams_ndjson_and_sends_options():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        lines = [
            {"message": {"role": "assistant", "content": "Hello"}, "done": False},
            {"message": {"role": "assistant", "content": " there"}, "done": False},
            {
                "message": {"content": ""},
                "done": True,
                "prompt_eval_count": 42,
                "eval_count": 2,
                "eval_duration": 1e9,
            },
        ]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines))

    stats = GenerationStats()
    tokens = [t async for t in backend(handler).stream(MESSAGES, OPTIONS, stats)]
    assert tokens == ["Hello", " there"]
    assert seen["model"] == "phi3-medquad" and seen["stream"] is True
    assert seen["options"] == {"num_ctx": 4096, "num_predict": 768, "temperature": 0.2}
    assert seen["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "hi"},
    ]
    assert (stats.prompt_tokens, stats.completion_tokens, stats.extra["tokens_per_s"]) == (
        42,
        2,
        2.0,
    )


async def test_model_missing_404():
    def handler(request):
        return httpx.Response(404, json={"error": "model 'phi3-medquad' not found"})

    with pytest.raises(ModelMissing):
        [t async for t in backend(handler).stream(MESSAGES, OPTIONS, GenerationStats())]


async def test_connection_refused_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LlmUnavailable):
        [t async for t in backend(handler).stream(MESSAGES, OPTIONS, GenerationStats())]


@pytest.mark.parametrize(
    ("models", "expected"),
    [(["phi3-medquad:latest", "llama3.2:latest"], "ok"), (["llama3.2:latest"], "model_missing")],
)
async def test_health_checks_installed_models(models, expected):
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": n} for n in models]})

    health = await backend(handler).health()
    assert health.status == expected and health.model == "phi3-medquad"
    assert (health.hint is None) == (expected == "ok")


async def test_health_unavailable_when_ollama_down():
    def handler(request):
        raise httpx.ConnectError("refused")

    health = await backend(handler).health()
    assert health.status == "unavailable" and "ollama serve" in health.hint
