"""Retrieval quality with the real local embedding model (skipped if it isn't downloaded)."""

import pytest

from pha.config import REPO_ROOT, Settings
from pha.rag.embedder import SentenceTransformerEmbedder
from tests.rag_helpers import fixture_bytes, make_service

MODEL_DIR = REPO_ROOT / "models" / "embeddings" / "bge-small-en-v1.5"
pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / "config.json").is_file(),
    reason="embedding model not downloaded (run scripts/fetch_embeddings.py)",
)


@pytest.fixture(scope="module")
def embedder():
    return SentenceTransformerEmbedder(MODEL_DIR)


@pytest.fixture
def service(tmp_path, embedder):
    # Use the production threshold so this test guards the default value.
    default_threshold = Settings.model_fields["min_score"].default
    svc = make_service(tmp_path, embedder=embedder, min_score=default_threshold)
    for name in ("lab-report.pdf", "visit-summary.txt", "medication-list.docx"):
        svc.ingest(name, None, fixture_bytes(name))
    return svc


@pytest.mark.parametrize(
    ("question", "filename", "page"),
    [
        ("what was my A1C?", "lab-report.pdf", 2),
        ("is my LDL cholesterol high?", "lab-report.pdf", 2),
        ("what dose of atorvastatin do I take?", "medication-list.docx", 1),
        ("am I allergic to any medicines?", "medication-list.docx", 1),
        ("what was my blood pressure at the visit?", "visit-summary.txt", 1),
    ],
)
def test_top_hit_is_the_right_page(service, question, filename, page):
    top = service.retriever.search(question)[0]
    assert (top.filename, top.page) == (filename, page)


UNRELATED = ["tips for running a marathon", "what is the capital of France?"]


@pytest.mark.parametrize("question", UNRELATED)
def test_unrelated_questions_filtered_by_default_threshold(service, question):
    assert service.retriever.search(question) == []
