"""Deterministic stand-in for the model, for tests and offline UI work (PHA_LLM_BACKEND=fake)."""

import asyncio
from collections.abc import AsyncIterator, Callable

from pha.llm.base import ChatMessage, GenerationOptions, GenerationStats, LlmError, LlmHealth

Reply = str | Callable[[list[ChatMessage]], str]


class FakeLLM:
    def __init__(
        self,
        reply: Reply = "This is a fake answer from the test model.",
        *,
        model: str = "fake",
        status: str = "ok",
        fail_after: int | None = None,
        error: LlmError | None = None,
        delay_s: float = 0.0,
    ):
        self.model = model
        self.reply = reply
        self.status = status
        self.fail_after = fail_after  # raise `error` after this many tokens
        self.error = error
        self.delay_s = delay_s
        self.calls: list[tuple[list[ChatMessage], GenerationOptions]] = []
        self.cancelled = False

    async def stream(
        self, messages: list[ChatMessage], options: GenerationOptions, stats: GenerationStats
    ) -> AsyncIterator[str]:
        self.calls.append((messages, options))
        if self.error is not None and self.fail_after is None:
            raise self.error
        text = self.reply(messages) if callable(self.reply) else self.reply
        tokens = text.split(" ")
        try:
            for i, token in enumerate(tokens):
                if self.fail_after is not None and i == self.fail_after:
                    raise self.error or LlmError("fake failure")
                if self.delay_s:
                    await asyncio.sleep(self.delay_s)
                yield token if i == len(tokens) - 1 else token + " "
        except (asyncio.CancelledError, GeneratorExit):
            self.cancelled = True
            raise
        stats.prompt_tokens = sum(len(m.content) for m in messages) // 4
        stats.completion_tokens = len(tokens)

    async def health(self) -> LlmHealth:
        hint = None if self.status == "ok" else f"fake status {self.status}"
        return LlmHealth(self.status, self.model, hint)  # type: ignore[arg-type]

    async def aclose(self) -> None:
        return None
