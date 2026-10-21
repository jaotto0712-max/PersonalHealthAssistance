import pytest
from pydantic import ValidationError

from pha.config import Settings


def test_defaults():
    s = Settings()
    assert (s.host, s.port) == ("127.0.0.1", 8000)
    assert s.ollama_url == "http://127.0.0.1:11434"
    assert s.model == "phi3-medquad-v3"


def test_env_override(monkeypatch):
    monkeypatch.setenv("PHA_MODEL", "phi3-base")
    assert Settings().model == "phi3-base"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_hosts_allowed(monkeypatch, host):
    monkeypatch.setenv("PHA_HOST", host)
    assert Settings().host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com", "::"])
def test_non_loopback_host_rejected(monkeypatch, host):
    monkeypatch.setenv("PHA_HOST", host)
    with pytest.raises(ValidationError, match="loopback"):
        Settings()


@pytest.mark.parametrize(
    "url", ["http://example.com:11434", "http://10.0.0.5:11434", "https://0.0.0.0:11434"]
)
def test_remote_ollama_rejected(monkeypatch, url):
    monkeypatch.setenv("PHA_OLLAMA_URL", url)
    with pytest.raises(ValidationError, match="model server must be local"):
        Settings()


def test_app_refuses_to_start_with_public_host(monkeypatch):
    from pha.config import get_settings
    from pha.main import create_app

    monkeypatch.setenv("PHA_HOST", "0.0.0.0")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        create_app()
