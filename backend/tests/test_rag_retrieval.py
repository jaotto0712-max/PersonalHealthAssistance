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
