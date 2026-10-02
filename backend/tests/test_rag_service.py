import contextlib
import json

from tests.rag_helpers import fixture_bytes, make_service


def test_ingest_indexes_chunks_with_page_metadata(tmp_path):
    svc = make_service(tmp_path)
    result = svc.ingest("lab-report.pdf", "application/pdf", fixture_bytes("lab-report.pdf"))
    record = result.record
    assert result.created and record.status == "indexed" and record.pages == 3
    assert record.chunks == svc.store.chunk_count(record.id) > 0
    hits = svc.store.query(svc.embedder.embed_query("LDL cholesterol"), k=10)
    assert {h.page for h in hits} <= {1, 2, 3}
    assert all(h.doc_id == record.id for h in hits)
    assert (tmp_path / "uploads" / record.id / "lab-report.pdf").is_file()


def test_needs_ocr_document_is_stored_but_not_indexed(tmp_path):
    svc = make_service(tmp_path)
    record = svc.ingest("scan.pdf", None, fixture_bytes("scanned-letter.pdf")).record
    assert record.status == "needs_ocr" and record.chunks == 0
    assert svc.store.count() == 0
    assert svc.list() == [record]


def test_duplicate_upload_returns_existing_record(tmp_path):
    svc = make_service(tmp_path)
    data = fixture_bytes("visit-summary.txt")
    first = svc.ingest("visit-summary.txt", "text/plain", data)
    count = svc.store.count()
    second = svc.ingest("renamed.txt", "text/plain", data)
    assert not second.created and second.record.id == first.record.id
    assert svc.store.count() == count and len(svc.list()) == 1


def test_registry_persists_across_restarts(tmp_path):
    svc = make_service(tmp_path)
    record = svc.ingest("visit-summary.txt", None, fixture_bytes("visit-summary.txt")).record
    reopened = make_service(tmp_path)
    assert [r.id for r in reopened.list()] == [record.id]
    assert reopened.registry.find_by_hash(record.sha256) is not None


def test_delete_removes_file_vectors_and_record(tmp_path):
    svc = make_service(tmp_path)
    keep = svc.ingest("visit-summary.txt", None, fixture_bytes("visit-summary.txt")).record
    gone = svc.ingest("lab-report.pdf", None, fixture_bytes("lab-report.pdf")).record
    assert svc.delete(gone.id)
    assert not (tmp_path / "uploads" / gone.id).exists()
    assert svc.store.chunk_count(gone.id) == 0
    assert all(h.doc_id == keep.id for h in svc.retriever.search("LDL cholesterol hemoglobin"))
    assert [r.id for r in svc.list()] == [keep.id]
    assert not svc.delete(gone.id)


def test_clear_removes_everything(tmp_path):
    svc = make_service(tmp_path)
    for name in ("visit-summary.txt", "lab-report.pdf"):
        svc.ingest(name, None, fixture_bytes(name))
    svc.clear()
    assert svc.list() == [] and svc.store.count() == 0
    assert list((tmp_path / "uploads").iterdir()) == []


def test_failed_ingest_leaves_no_residue(tmp_path):
    class ExplodingEmbedder:
        def embed_documents(self, texts):
            raise RuntimeError("boom")

        def embed_query(self, text):
            return []

    svc = make_service(tmp_path, embedder=ExplodingEmbedder())
    with contextlib.suppress(RuntimeError):
        svc.ingest("visit-summary.txt", None, fixture_bytes("visit-summary.txt"))
    assert svc.list() == [] and svc.store.count() == 0
    assert not any((tmp_path / "uploads").iterdir())


def test_reconcile_removes_orphans_and_keeps_needs_ocr(tmp_path):
    svc = make_service(tmp_path)
    ocr = svc.ingest("scan.pdf", None, fixture_bytes("scanned-letter.pdf")).record
    lost_file = svc.ingest("visit-summary.txt", None, fixture_bytes("visit-summary.txt")).record
    orphan_vectors = svc.ingest("lab-report.pdf", None, fixture_bytes("lab-report.pdf")).record

    # Simulate crashes/manual tampering:
    (tmp_path / "uploads" / lost_file.id / "visit-summary.txt").unlink()
    (tmp_path / "uploads" / lost_file.id).rmdir()  # file gone, record + vectors remain
    svc.registry.remove(orphan_vectors.id)  # record gone, file + vectors remain
    (tmp_path / "uploads" / "stray-dir").mkdir()

    svc.reconcile()

    assert [r.id for r in svc.list()] == [ocr.id]  # needs_ocr doc (file, no chunks) is kept
    assert svc.store.doc_ids() == set()
    assert sorted(p.name for p in (tmp_path / "uploads").iterdir()) == [ocr.id]
    stored = json.loads((tmp_path / "documents.json").read_text())
    assert [r["id"] for r in stored] == [ocr.id]
