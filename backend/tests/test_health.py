from pha import __version__


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["version"] == __version__
    assert body["llm"] == "ok"  # fake backend in tests
