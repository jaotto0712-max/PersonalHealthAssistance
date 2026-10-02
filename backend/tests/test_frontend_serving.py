from fastapi.testclient import TestClient

from pha.config import get_settings
from pha.main import create_app


def _client(monkeypatch, dist) -> TestClient:
    monkeypatch.setenv("PHA_FRONTEND_DIST", str(dist))
    get_settings.cache_clear()
    return TestClient(create_app())


def test_serves_built_frontend_at_root(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>PHA</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    client = _client(monkeypatch, tmp_path)

    root = client.get("/")
    assert root.status_code == 200
    assert "<title>PHA</title>" in root.text
    assert client.get("/assets/app.js").status_code == 200


def test_api_routes_take_priority_over_static(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html>")
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/health").json()["status"] == "ok"


def test_no_frontend_build_means_api_only(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path / "missing")
    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
