from pha.config import Settings
from pha.llm.base import GenerationOptions, LLMBackend
from pha.llm.fake import FakeLLM
from pha.llm.ollama import OllamaBackend

FAKE_REPLY = (
    "This is a placeholder answer from the fake model (PHA_LLM_BACKEND=fake). "
    "Start Ollama and set PHA_LLM_BACKEND=ollama for real answers."
)


def build_llm(settings: Settings) -> LLMBackend:
    if settings.llm_backend == "fake":
        return FakeLLM(FAKE_REPLY, model=f"fake ({settings.model})")
    return OllamaBackend(settings.ollama_url, settings.model, settings.llm_timeout_s)


def generation_options(settings: Settings) -> GenerationOptions:
    return GenerationOptions(
        num_ctx=settings.num_ctx, num_predict=settings.num_predict, temperature=settings.temperature
    )
