"""Privacy verification: the network guard, and a full offline session under it.

The guard tests run in subprocesses with PHA_NET_GUARD=1, exactly as a user would enable it.
The end-to-end test needs the local embedding model and Ollama with the app's model installed;
it is skipped (with the reason) when either is missing, e.g. in CI.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from pha.config import REPO_ROOT, Settings
from pha.rag.store import VectorStore
from tests.test_chat_api import parse_sse

BACKEND = REPO_ROOT / "backend"
UNIQUE = "Zorvanite"  # an invented analyte: only the uploaded test document mentions it
DOCUMENT = (
    f"Lab results, 05/01/2026.\n{UNIQUE} level: 42 units (reference 10-30), flagged High.\n"
    "Comment: synthetic document for the privacy test.\n"
)


def guarded_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PHA_")}
    env.update(
        PHA_NET_GUARD="1",
        PHA_NET_GUARD_LOG=str(tmp_path / "netguard.log"),
        PYTHONPATH=str(BACKEND),
        **extra,
    )
    return env


def guard_log(tmp_path: Path) -> list[dict]:
    path = tmp_path / "netguard.log"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


# --- 5.3: the guard catches outbound attempts ----------------------------------------------

PROBE = """
import socket, urllib.request
import pha  # installs the guard from PHA_NET_GUARD
results = {}
try:
    urllib.request.urlopen("http://example.com/", timeout=3)
    results["http"] = "connected"
except OSError as e:
    results["http"] = type(e).__name__ + ": " + str(e)
s = socket.socket()
try:
    s.connect(("93.184.215.14", 80))
    results["ip"] = "connected"
except OSError as e:
    results["ip"] = type(e).__name__
finally:
    s.close()
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
c = socket.socket(); c.connect(srv.getsockname()); c.close(); srv.close()
results["loopback"] = "connected"
print(results)
"""


def test_guard_blocks_and_logs_outbound_attempts(tmp_path):
    out = subprocess.run(
        [sys.executable, "-c", PROBE],
        env=guarded_env(tmp_path),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    results = eval(out.stdout.strip().splitlines()[-1])  # noqa: S307  (our own repr)
    assert results["http"] != "connected" and "network guard" in results["http"]
    assert results["ip"] == "BlockedConnection"
    assert results["loopback"] == "connected"
    destinations = [e["destination"] for e in guard_log(tmp_path)]
    assert "example.com:80" in destinations and "93.184.215.14:80" in destinations
    assert not any(d.startswith("127.") for d in destinations)


def test_guard_is_off_unless_enabled(tmp_path):
    code = "import socket, pha; print(getattr(socket.socket.connect, '__module__', 'builtin'))"
    env = guarded_env(tmp_path)
    del env["PHA_NET_GUARD"]
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "netguard" not in out.stdout


# --- 5.2: a full session under the guard ---------------------------------------------------


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def local_stack_missing() -> str | None:
    # the app's defaults (conftest points PHA_* at temp paths, so don't read the environment)
    settings = Settings.model_construct()
    if not (settings.embed_model_dir / "config.json").is_file():
        return f"embedding model not found at {settings.embed_model_dir}"
    try:
        tags = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2).json()
    except httpx.HTTPError:
        return "Ollama is not running"
    names = {m["name"].removesuffix(":latest") for m in tags.get("models", [])}
    if settings.model not in names:
        return f"Ollama model {settings.model} is not installed"
    return None


def test_full_session_makes_no_outbound_connections_and_leaves_no_residue(tmp_path):
    if reason := local_stack_missing():
        pytest.skip(reason)
    data = tmp_path / "data"
    port = free_port()
    env = guarded_env(
        tmp_path,
        PHA_CHROMA_DIR=str(data / "chroma"),
        PHA_UPLOADS_DIR=str(data / "uploads"),
        PHA_REGISTRY_PATH=str(data / "documents.json"),
        PHA_CHATS_PATH=str(data / "chats.db"),
        PHA_NUM_PREDICT="96",  # the answer's content isn't under test; keep the run short
    )
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "pha.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        cwd=tmp_path,  # no .env file here
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}/api"
    try:
        with httpx.Client(base_url=base, timeout=180) as api:
            deadline = time.monotonic() + 90
            while True:
                try:
                    if api.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                assert server.poll() is None, server.stdout.read()
                assert time.monotonic() < deadline, "backend did not start"
                time.sleep(0.3)

            files = {"file": ("privacy-test.txt", DOCUMENT.encode(), "text/plain")}
            doc = api.post("/documents", files=files).json()
            assert doc["status"] == "indexed" and doc["chunks"] >= 1

            conv = api.post("/conversations").json()
            question = f"What was my {UNIQUE} level?"
            reply = parse_sse(
                api.post("/chat", json={"message": question, "conversation_id": conv["id"]}).text
            )
            names = [n for n, _ in reply]
            assert names[0] == "meta" and names[-1] == "done", reply[-1]
            assert reply[0][1]["retrieved_count"] >= 1
            sources = next(d["items"] for n, d in reply if n == "sources")
            assert any(s["filename"] == "privacy-test.txt" for s in sources)
            assert "".join(d["text"] for n, d in reply if n == "token").strip()  # model answered

            assert api.delete(f"/documents/{doc['id']}").status_code == 204
            assert not (data / "uploads" / doc["id"]).exists()
            assert api.get("/documents").json() == []
            again = parse_sse(api.post("/chat", json={"message": question}).text)
            assert again[0][1]["retrieved_count"] == 0
            assert not any(n == "sources" and d["items"] for n, d in again)

            assert api.delete(f"/conversations/{conv['id']}").status_code == 204
    finally:
        server.terminate()
        output = server.communicate(timeout=30)[0]

    blocked = guard_log(tmp_path)
    assert blocked == [], f"outbound attempts: {[e['destination'] for e in blocked]}\n{output}"
    assert (tmp_path / "netguard.log").exists(), "the guard was not active in the backend"
    store = VectorStore(data / "chroma")
    assert doc["id"] not in store.doc_ids() and store.count() == 0
