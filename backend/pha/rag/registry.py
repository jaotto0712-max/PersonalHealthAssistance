"""Document metadata registry: a small JSON file, the source of truth for what is uploaded."""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["indexed", "needs_ocr"]


class DocumentRecord(BaseModel):
    id: str
    filename: str
    sha256: str = Field(exclude=True)  # internal: duplicate detection, not part of the API
    size_bytes: int
    pages: int
    chunks: int
    status: DocumentStatus
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extractor_version: int = Field(default=1, exclude=True)  # records before versioning = 1


class Registry:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._records: dict[str, DocumentRecord] = {}
        if path.is_file():
            raw = json.loads(path.read_text())
            self._records = {r["id"]: DocumentRecord.model_validate(r) for r in raw}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            r.model_dump(mode="json")
            | {"sha256": r.sha256, "extractor_version": r.extractor_version}
            for r in self.all()
        ]
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)  # atomic on POSIX

    def all(self) -> list[DocumentRecord]:
        return sorted(self._records.values(), key=lambda r: r.uploaded_at)

    def get(self, doc_id: str) -> DocumentRecord | None:
        return self._records.get(doc_id)

    def find_by_hash(self, sha256: str) -> DocumentRecord | None:
        return next((r for r in self._records.values() if r.sha256 == sha256), None)

    def add(self, record: DocumentRecord) -> None:
        with self._lock:
            self._records[record.id] = record
            self._save()

    def remove(self, doc_id: str) -> None:
        with self._lock:
            if self._records.pop(doc_id, None) is not None:
                self._save()

    def clear(self) -> None:
        with self._lock:
            self._records = {}
            self._save()
