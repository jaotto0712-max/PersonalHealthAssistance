from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

LlmStatus = Literal["ok", "unavailable", "model_missing"]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class GenerationOptions:
    num_ctx: int
    num_predict: int
    temperature: float


@dataclass(frozen=True)
class LlmHealth:
    status: LlmStatus
    model: str
    hint: str | None = None


@dataclass
class GenerationStats:
    """Filled in by the backend when generation finishes (if it reports them)."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    extra: dict[str, float] = field(default_factory=dict)


class LlmError(Exception):
    code = "llm_error"


class LlmUnavailable(LlmError):
    code = "llm_unavailable"


class ModelMissing(LlmError):
    code = "model_missing"


class LLMBackend(Protocol):
    model: str

    def stream(
        self, messages: list[ChatMessage], options: GenerationOptions, stats: GenerationStats
    ) -> AsyncIterator[str]: ...

    async def health(self) -> LlmHealth: ...

    async def aclose(self) -> None: ...
