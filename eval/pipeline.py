"""Builds the app's real chat pipeline for evaluation, over temporary storage (never data/)."""

import hashlib
import json
import tempfile
import time
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pha  # noqa: F401  (applies the offline policy before ML imports)
from pha.chat.orchestrator import ChatOrchestrator
from pha.chat.prompt import load_system_prompt
from pha.config import REPO_ROOT, get_settings
from pha.llm.base import ChatMessage, GenerationOptions
from pha.llm.ollama import OllamaBackend
from pha.rag.embedder import SentenceTransformerEmbedder
from pha.rag.parsers import EXTRACTOR_VERSION
from pha.rag.registry import Registry
from pha.rag.service import DocumentService
from pha.rag.store import VectorStore

FIXTURES = REPO_ROOT / "eval" / "fixtures" / "docs"
SEED = 0


@dataclass
class Outcome:
    answer: str = ""
    cited_files: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    retrieved: int = 0
    emergency: bool = False
    stopped_early: bool = False
    stop_reason: str | None = None
    error: str | None = None
    ttft_s: float | None = None
    total_s: float = 0.0
    completion_tokens: int | None = None
    tokens_per_s: float | None = None


class Harness:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.system_prompt = load_system_prompt(self.settings.system_prompt_path)
        self.embedder = SentenceTransformerEmbedder(self.settings.embed_model_dir)
        self._tmp = tempfile.TemporaryDirectory(prefix="pha-eval-")
        self._services: dict[tuple[str, ...], DocumentService] = {}
        self.options = GenerationOptions(
            num_ctx=self.settings.num_ctx,
            num_predict=self.settings.num_predict,
            temperature=self.settings.temperature,
            seed=SEED,
        )

    def documents(self, docs: Iterable[str]) -> DocumentService:
        """A document store holding exactly these fixtures (cached per set of names)."""
        key = tuple(sorted(docs))
        if key not in self._services:
            root = Path(self._tmp.name) / (hashlib.sha1("|".join(key).encode()).hexdigest()[:10])
            s = self.settings
            svc = DocumentService(
                embedder=self.embedder, store=VectorStore(root / "chroma"),
                registry=Registry(root / "documents.json"), uploads_dir=root / "uploads",
                chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap,
                max_upload_bytes=s.max_upload_bytes, top_k=s.top_k, min_score=s.min_score,
            )  # fmt: skip
            for name in key:
                svc.ingest(name, None, (FIXTURES / name).read_bytes())
            self._services[key] = svc
        return self._services[key]

    def orchestrator(self, model: str, docs: Iterable[str] | None) -> ChatOrchestrator:
        """docs=None means retrieval off (closed-book)."""
        llm = OllamaBackend(self.settings.ollama_url, model, self.settings.llm_timeout_s)
        retriever = None if docs is None else self.documents(docs).retriever
        return ChatOrchestrator(llm, retriever, self.system_prompt, self.options)

    async def ask(
        self, orchestrator: ChatOrchestrator, question: str, history: list[dict]
    ) -> Outcome:
        out = Outcome()
        turns = [ChatMessage(t["role"], t["content"]) for t in history]
        start = time.perf_counter()
        text: list[str] = []
        async for event in orchestrator.run(question, turns):
            if event.name == "meta":
                out.retrieved = event.data.get("retrieved_count", 0)
                out.emergency = bool(event.data.get("emergency"))
            elif event.name == "token":
                out.ttft_s = out.ttft_s or time.perf_counter() - start
                text.append(event.data["text"])
            elif event.name == "sources":
                out.sources = event.data["items"]
                out.cited_files = sorted({s["filename"] for s in out.sources if s["cited"]})
            elif event.name == "done":
                usage = event.data.get("usage", {})
                out.stopped_early = bool(usage.get("stopped_early"))
                out.stop_reason = usage.get("stop_reason")
                out.completion_tokens = usage.get("completion_tokens")
                out.tokens_per_s = usage.get("tokens_per_s")
            elif event.name == "error":
                out.error = event.data["message"]
        out.answer = "".join(text)
        out.total_s = time.perf_counter() - start
        await orchestrator.llm.aclose()
        return out


def model_digests() -> dict[str, str]:
    url = get_settings().ollama_url + "/api/tags"
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 (loopback, validated)
        return {
            m["name"].removesuffix(":latest"): m["digest"][:12] for m in json.load(resp)["models"]
        }


def fingerprint(model_digest: str) -> str:
    """Changes whenever prompts, pipeline code, extractor, decoding or the model change."""
    h = hashlib.sha256()
    training, pha_dir = REPO_ROOT / "training", REPO_ROOT / "backend" / "pha"
    sources = [
        *training.glob("*_prompt*.txt"), *training.glob("*instructions.txt"),
        *(pha_dir / "chat").glob("*.py"), *(pha_dir / "rag").glob("*.py"),
    ]  # fmt: skip
    for path in sorted(sources):
        h.update(path.read_bytes())
    s = get_settings()
    h.update(
        f"{EXTRACTOR_VERSION}|{model_digest}|{s.num_ctx}|{s.num_predict}|{s.temperature}|{SEED}".encode()
    )
    return h.hexdigest()[:16]
