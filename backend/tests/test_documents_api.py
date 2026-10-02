import pytest
from fastapi.testclient import TestClient

from pha.main import create_app
from tests.rag_helpers import fixture_bytes, make_service

PDF = "application/pdf"


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


@pytest.fixture
def api(service):
    with TestClient(create_app(documents=service)) as client:
        yield client


def upload(api, name, data, content_type="application/octet-stream"):
    return api.post("/api/documents", files={"file": (name, data, content_type)})


def test_upload_returns_201_and_record(api):
    resp = upload(api, "lab-report.pdf", fixture_bytes("lab-report.pdf"), PDF)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"id", "filename", "size_bytes", "pages", "chunks", "status", "uploaded_at"}
    assert body["status"] == "indexed" and body["pages"] == 3 and body["chunks"] > 0


def test_list_after_uploads(api):
    upload(api, "lab-report.pdf", fixture_bytes("lab-report.pdf"), PDF)
    upload(api, "visit-summary.txt", fixture_bytes("visit-summary.txt"), "text/plain")
    names = [d["filename"] for d in api.get("/api/documents").json()]
    assert names == ["lab-report.pdf", "visit-summary.txt"]


def test_unsupported_type_rejected_and_not_stored(api, tmp_path):
    resp = upload(api, "tool.exe", b"MZ\x90\x00")
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]
    assert api.get("/api/documents").json() == []
    assert not (tmp_path / "uploads").exists() or not any((tmp_path / "uploads").iterdir())


def test_oversized_file_rejected(tmp_path):
    svc = make_service(tmp_path, max_upload_bytes=1024)
    with TestClient(create_app(documents=svc)) as client:
        resp = upload(client, "big.pdf", b"%PDF" + b"0" * 5000, PDF)
        assert resp.status_code == 413
        assert "larger than" in resp.json()["detail"]
        assert client.get("/api/documents").json() == []


def test_oversized_request_rejected_early_by_content_length(tmp_path):
    svc = make_service(tmp_path, max_upload_bytes=1024)
    with TestClient(create_app(documents=svc)) as client:
        resp = upload(client, "big.pdf", b"0" * (200 * 1024), PDF)
        assert resp.status_code == 413


def test_unreadable_pdf_returns_422(api):
    resp = upload(api, "broken.pdf", b"%PDF-1.4 not a pdf", PDF)
    assert resp.status_code == 422


def test_path_traversal_filename_is_sanitized(api, tmp_path):
    resp = upload(api, "../../etc/passwd.txt", b"harmless text", "text/plain")
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["filename"] == "passwd.txt"
    assert (tmp_path / "uploads" / doc["id"] / "passwd.txt").is_file()
    assert not (tmp_path / "etc").exists()


def test_duplicate_upload_returns_existing_with_200(api, service):
    first = upload(api, "visit-summary.txt", fixture_bytes("visit-summary.txt"), "text/plain")
    count = service.store.count()
    second = upload(api, "copy.txt", fixture_bytes("visit-summary.txt"), "text/plain")
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert service.store.count() == count


def test_needs_ocr_status_exposed(api):
    resp = upload(api, "scan.pdf", fixture_bytes("scanned-letter.pdf"), PDF)
    assert resp.status_code == 201
    assert resp.json()["status"] == "needs_ocr" and resp.json()["chunks"] == 0


def test_delete_document(api, service, tmp_path):
    doc = upload(api, "lab-report.pdf", fixture_bytes("lab-report.pdf"), PDF).json()
    assert api.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert api.get("/api/documents").json() == []
    assert not (tmp_path / "uploads" / doc["id"]).exists()
    assert service.store.chunk_count(doc["id"]) == 0
    assert service.retriever.search("LDL cholesterol HDL triglycerides") == []


def test_delete_unknown_document_404(api):
    assert api.delete("/api/documents/does-not-exist").status_code == 404


def test_clear_all(api, service):
    upload(api, "lab-report.pdf", fixture_bytes("lab-report.pdf"), PDF)
    upload(api, "visit-summary.txt", fixture_bytes("visit-summary.txt"), "text/plain")
    assert api.delete("/api/documents").status_code == 204
    assert api.get("/api/documents").json() == []
    assert service.store.count() == 0


def test_documents_unavailable_without_embedding_model(client):
    # `client` builds the app from settings; conftest points the model dir at a missing path.
    resp = client.get("/api/documents")
    assert resp.status_code == 503
    assert "fetch_embeddings.py" in resp.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_startup_reconciles_storage(tmp_path):
    svc = make_service(tmp_path)
    record = svc.ingest("visit-summary.txt", None, fixture_bytes("visit-summary.txt")).record
    svc.registry.remove(record.id)  # orphan: file + vectors without a record
    with TestClient(create_app(documents=svc)):
        pass
    assert svc.store.doc_ids() == set()
    assert not (tmp_path / "uploads" / record.id).exists()
