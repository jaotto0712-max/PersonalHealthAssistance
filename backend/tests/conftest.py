import socket

import pytest
from fastapi.testclient import TestClient

from pha.config import get_settings
from pha.offline import is_loopback_host


class OutboundConnectionError(AssertionError):
    """Raised when code under test tries to reach a non-loopback address."""


@pytest.fixture(autouse=True)
def socket_guard(monkeypatch):
    """Fail any test that opens a connection to a non-loopback address."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _check(address):
        if isinstance(address, tuple) and not is_loopback_host(str(address[0])):
            raise OutboundConnectionError(f"outbound connection blocked: {address!r}")

    def guarded_connect(self, address):
        _check(address)
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        _check(address)
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch, tmp_path):
    """Isolate tests from a developer's PHA_* env vars, .env file, and real data/ directory.

    The embedding model is pointed at a missing directory and the LLM is the fake backend,
    so tests never load real models or need Ollama unless they opt in explicitly.
    """
    import os

    for key in list(os.environ):
        if key.startswith("PHA_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(os.path.dirname(__file__))  # no .env here
    monkeypatch.setenv("PHA_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("PHA_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("PHA_REGISTRY_PATH", str(tmp_path / "documents.json"))
    monkeypatch.setenv("PHA_EMBED_MODEL_DIR", str(tmp_path / "no-embedding-model"))
    monkeypatch.setenv("PHA_LLM_BACKEND", "fake")  # tests never depend on a running Ollama
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    from pha.main import create_app

    with TestClient(create_app()) as c:
        yield c
