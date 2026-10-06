from pha.rag.keyword import bm25_rank, tokens
from tests.rag_helpers import make_service


class FlatEmbedder:
    """Every text gets the same vector: vector ranking carries no signal at all."""

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


def test_tokens_drop_question_words_and_keep_lab_names():
    assert tokens("What was my BUN and my eGFR?") == ["bun", "egfr"]
    assert tokens("A1C 6.1% on 0.76-1.27") == ["a1c", "6.1", "0.76", "1.27"]


def test_rare_term_ranks_its_document_first():
    docs = ["Glucose 94 mg/dL. Sodium 141.", "BUN 24 mg/dL high.", "Sodium 139. Glucose 101."]
    assert bm25_rank("What was my BUN?", docs)[0][0] == 1
    assert bm25_rank("hello there", docs) == []


def test_keyword_search_finds_exact_names_when_vectors_cannot(tmp_path):
    svc = make_service(tmp_path, embedder=FlatEmbedder(), top_k=1)
    for i, text in enumerate(
        ["Lipid panel. LDL 162 mg/dL.", "Thyroid. TSH 2.1 mIU/L.", "CBC. WBC 6.2"]
    ):
        svc.ingest(f"doc{i}.txt", None, text.encode())
    assert svc.retriever.search("What was my TSH?")[0].filename == "doc1.txt"
    svc.retriever.keyword = False
    # without keywords the flat vectors give an arbitrary order (documented, not asserted)
    assert len(svc.retriever.search("What was my TSH?")) == 1


def test_keyword_hits_still_need_the_similarity_floor(tmp_path):
    text = b"Thyroid panel. TSH 2.1 mIU/L. Free T4 1.2 ng/dL."
    low = make_service(tmp_path / "low", min_score=0.0)
    low.ingest("labs.txt", None, text)
    assert low.retriever.search("TSH")  # the keyword match exists
    high = make_service(tmp_path / "high", min_score=0.99)  # nothing is this similar
    high.ingest("labs.txt", None, text)
    assert high.retriever.search("TSH") == []  # the keyword match alone doesn't pass the floor
