from tests.rag_helpers import fixture_bytes, make_service


def test_relevant_chunk_retrieved_with_citation_metadata(tmp_path):
    svc = make_service(tmp_path)
    svc.ingest("labs.txt", None, b"Hemoglobin A1C: 6.1%\nVitamin B12: 450 pg/mL")
    svc.ingest("visit.txt", None, b"Discussed exercise and a walking plan with the patient.")
    hits = svc.retriever.search("what was my A1C?")
    assert hits and hits[0].filename == "labs.txt" and hits[0].page == 1
    assert "6.1%" in hits[0].text


def test_lab_report_page_is_found(tmp_path):
    svc = make_service(tmp_path)
    svc.ingest("lab-report.pdf", None, fixture_bytes("lab-report.pdf"))
    top = svc.retriever.search("LDL cholesterol HDL triglycerides")[0]
    assert (top.filename, top.page) == ("lab-report.pdf", 2)


def test_unrelated_query_is_filtered_by_threshold(tmp_path):
    svc = make_service(tmp_path)
    svc.ingest("lab-report.pdf", None, fixture_bytes("lab-report.pdf"))
    assert svc.retriever.search("how do vaccines work?") == []


def test_no_documents_returns_empty(tmp_path):
    assert make_service(tmp_path).retriever.search("anything") == []


def test_results_ordered_by_descending_score(tmp_path):
    svc = make_service(tmp_path, min_score=0.0)
    for name in ("lab-report.pdf", "visit-summary.txt", "medication-list.docx"):
        svc.ingest(name, None, fixture_bytes(name))
    hits = svc.retriever.search("cholesterol atorvastatin blood pressure")
    assert len(hits) == 4
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def _two_docs(tmp_path):
    svc = make_service(tmp_path)
    svc.ingest("kidney.txt", None, b"Kidney panel. BUN 24 mg/dL high. Creatinine 1.31 mg/dL.")
    svc.ingest("lipids.txt", None, b"Lipid panel. LDL cholesterol 162 mg/dL. HDL 48 mg/dL.")
    return svc


def test_follow_up_searches_with_the_previous_message(tmp_path):
    svc = _two_docs(tmp_path)
    alone = svc.retriever.search("What should it be below?")
    assert not any(h.filename == "kidney.txt" for h in alone)  # nothing to search with
    hits = svc.retriever.search("What should it be below?", previous="What was my BUN?")
    assert hits and hits[0].filename == "kidney.txt"


def test_self_contained_question_ignores_the_previous_message(tmp_path):
    svc = _two_docs(tmp_path)
    hits = svc.retriever.search("What was my LDL cholesterol?", previous="What was my BUN?")
    assert [h.filename for h in hits] == ["lipids.txt"]


def test_history_words_cover_everyday_phrasings():
    from pha.rag.retriever import HISTORY_QUERY

    for q in [
        "Is it going up?",
        "Was it better on my last test?",
        "Is it improving?",
        "Has it changed?",
    ]:
        assert HISTORY_QUERY.search(q), q
    for q in ["What was my BUN?", "Is that high?", "What should it be?"]:
        assert not HISTORY_QUERY.search(q), q
