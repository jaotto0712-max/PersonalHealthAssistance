"""Document lifecycle: validate → store file → parse → chunk → embed → index; delete; reconcile."""

import hashlib
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pha.rag.chunker import chunk_pages
from pha.rag.embedder import Embedder
from pha.rag.parsers import parse
from pha.rag.registry import DocumentRecord, Registry
from pha.rag.retriever import Retriever
from pha.rag.store import VectorStore

log = logging.getLogger(__name__)

# Extension -> acceptable client-declared MIME types. Browsers often send octet-stream or
# nothing for .md/.docx, so those are tolerated; a clearly different type is rejected.
ALLOWED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
}
GENERIC_TYPES = {"", "application/octet-stream"}


class UnsupportedFileType(ValueError):
    pass


class FileTooLarge(ValueError):
    pass


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def sanitize_filename(name: str, extension: str) -> str:
    """Basename only, safe characters only; never trust client-supplied paths."""
    base = PurePosixPath(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    stem = base[: -len(extension)] if base.lower().endswith(extension) else base
    stem = stem.strip(" .")[:120] or "document"
    return f"{stem}{extension}"


def validate_upload(filename: str, content_type: str | None, size: int, max_bytes: int) -> str:
    """Return the normalized extension, or raise UnsupportedFileType / FileTooLarge."""
    extension = PurePosixPath(filename.lower()).suffix
    if extension not in ALLOWED_TYPES:
        raise UnsupportedFileType("Unsupported file type. Use PDF, TXT, MD, or DOCX.")
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_TYPES[extension] | GENERIC_TYPES:
        raise UnsupportedFileType(f"File content type {mime!r} does not match {extension}.")
    if size > max_bytes:
        raise FileTooLarge(f"File is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    return extension


@dataclass
class IngestResult:
    record: DocumentRecord
    created: bool  # False when an identical file was already uploaded


class DocumentService:
    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        registry: Registry,
        uploads_dir: Path,
        chunk_size: int,
        chunk_overlap: int,
        max_upload_bytes: int,
        top_k: int,
        min_score: float,
    ):
        self.embedder = embedder
        self.store = store
        self.registry = registry
        self.uploads_dir = uploads_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_upload_bytes = max_upload_bytes
        self.retriever = Retriever(embedder, store, top_k=top_k, min_score=min_score)

    def ingest(self, filename: str, content_type: str | None, data: bytes) -> IngestResult:
        extension = validate_upload(filename, content_type, len(data), self.max_upload_bytes)
        digest = hashlib.sha256(data).hexdigest()
        if existing := self.registry.find_by_hash(digest):
            return IngestResult(existing, created=False)

        parsed = parse(data, extension)  # ParseError propagates before anything is written
        doc_id = uuid.uuid4().hex
        safe_name = sanitize_filename(filename, extension)
        doc_dir = self.uploads_dir / doc_id
        try:
            doc_dir.mkdir(parents=True)
            (doc_dir / safe_name).write_bytes(data)
            chunks = (
                []
                if parsed.needs_ocr
                else chunk_pages(parsed.pages, self.chunk_size, self.chunk_overlap)
            )
            if chunks:
                vectors = self.embedder.embed_documents([c.text for c in chunks])
                self.store.add(doc_id, safe_name, chunks, vectors)
            record = DocumentRecord(
                id=doc_id,
                filename=safe_name,
                sha256=digest,
                size_bytes=len(data),
                pages=parsed.page_count,
                chunks=len(chunks),
                status="needs_ocr" if parsed.needs_ocr else "indexed",
            )
            self.registry.add(record)  # last step: a record means file + vectors are complete
        except Exception:
            self.store.delete_document(doc_id)
            shutil.rmtree(doc_dir, ignore_errors=True)
            raise
        return IngestResult(record, created=True)

    def list(self) -> list[DocumentRecord]:
        return self.registry.all()

    def delete(self, doc_id: str) -> bool:
        if self.registry.get(doc_id) is None:
            return False
        self.store.delete_document(doc_id)  # vectors first: content is unsearchable immediately
        shutil.rmtree(self.uploads_dir / doc_id, ignore_errors=True)
        self.registry.remove(doc_id)
        return True

    def clear(self) -> None:
        self.store.clear()
        if self.uploads_dir.exists():
            for child in self.uploads_dir.iterdir():
                _remove_path(child)
        self.registry.clear()

    def reconcile(self) -> None:
        """Make registry, upload files, and vectors agree (the registry is the source of truth).

        Removes: records whose file is gone, upload dirs with no record, vectors with no record.
        """
        for record in self.registry.all():
            if not (self.uploads_dir / record.id).is_dir():
                log.warning("Removing document %s: its file is missing", record.id)
                self.registry.remove(record.id)
        known = {r.id for r in self.registry.all()}
        if self.uploads_dir.exists():
            for child in self.uploads_dir.iterdir():
                if child.name not in known:
                    log.warning("Removing unregistered upload %s", child.name)
                    _remove_path(child)
        for doc_id in self.store.doc_ids() - known:
            log.warning("Removing orphaned vectors for %s", doc_id)
            self.store.delete_document(doc_id)
