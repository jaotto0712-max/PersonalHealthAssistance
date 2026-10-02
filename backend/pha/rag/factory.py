"""Builds the document service from settings (used by the app lifespan)."""

from pha.config import Settings
from pha.rag.embedder import Embedder, SentenceTransformerEmbedder
from pha.rag.registry import Registry
from pha.rag.service import DocumentService
from pha.rag.store import VectorStore


def build_document_service(settings: Settings, embedder: Embedder | None = None) -> DocumentService:
    return DocumentService(
        embedder=embedder or SentenceTransformerEmbedder(settings.embed_model_dir),
        store=VectorStore(settings.chroma_dir),
        registry=Registry(settings.registry_path),
        uploads_dir=settings.uploads_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_upload_bytes=settings.max_upload_bytes,
        top_k=settings.top_k,
        min_score=settings.min_score,
    )
