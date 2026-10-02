"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pha import __version__
from pha.api.chat import router as chat_router
from pha.api.documents import router as documents_router
from pha.api.health import router as health_router
from pha.chat.orchestrator import ChatOrchestrator
from pha.chat.prompt import load_system_prompt
from pha.config import get_settings
from pha.llm.base import LLMBackend
from pha.llm.factory import build_llm, generation_options
from pha.rag.embedder import EmbeddingModelMissing
from pha.rag.factory import build_document_service
from pha.rag.service import DocumentService

log = logging.getLogger(__name__)


def create_app(documents: DocumentService | None = None, llm: LLMBackend | None = None) -> FastAPI:
    """Create the app. Pass `documents` / `llm` to inject prebuilt components (tests)."""
    settings = get_settings()  # validate configuration (loopback policy) before serving anything
    system_prompt = load_system_prompt(settings.system_prompt_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.documents, app.state.documents_error = documents, None
        if documents is None:
            try:
                app.state.documents = build_document_service(settings)
            except EmbeddingModelMissing as e:
                log.warning("Document features disabled: %s", e)
                app.state.documents_error = str(e)
        if app.state.documents is not None:
            app.state.documents.reconcile()

        app.state.llm = llm or build_llm(settings)
        retriever = app.state.documents.retriever if app.state.documents else None
        app.state.chat = ChatOrchestrator(
            app.state.llm, retriever, system_prompt, generation_options(settings)
        )
        try:
            yield
        finally:
            if llm is None:
                await app.state.llm.aclose()

    app = FastAPI(title="Personal Health Assistant", version=__version__, lifespan=lifespan)
    app.include_router(health_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    # Serve the built UI from the same local origin; mounted last so /api routes take priority.
    if (settings.frontend_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app


app = create_app()
