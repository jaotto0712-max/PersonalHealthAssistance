import json

from pha.rag.lab_tables import Word, is_boilerplate, page_text, twin_notes
from pha.rag.parsers import EXTRACTOR_VERSION, parse
from tests.rag_helpers import fixture_bytes, make_service

HEADER = [(36, "Test"), (191, "Current"), (219, "Result"), (325, "Previous"), (355, "Result"),
          (463, "Units"), (521, "Reference"), (557, "Interval")]  # fmt: skip


def row(top, cells, size=8.0):
    return [Word(text, x, top, size) for x, text in cells]


def test_column_fixture_reads_current_and_previous_correctly():
    pages = parse(fixture_bytes("lab-report-columns.pdf"), ".pdf").pages
    text = "\n".join(t for _, t in pages)
    lines = text.splitlines()
    assert "Creatinine: 0.98 mg/dL (reference 0.76-1.27)." in lines
    assert "Potassium: 5.6 mmol/L (reference 3.5-5.2), flagged High." in lines
    assert "Hemoglobin: 11.8 g/dL (reference 13.0-17.7), flagged Low." in lines
    assert "eGFR: 101 mL/min/1.73 (reference >59)." in lines
    assert (
        "Older results from 03/02/2026 (not current): Glucose 92 mg/dL; BUN 28 mg/dL; "
        "Creatinine 1.62 mg/dL; eGFR 52 mL/min/1.73; Potassium 4.4 mmol/L; Sodium 137 mmol/L."
    ) in lines
    # previous values never appear on a current-result line
    assert not any("(reference" in line and "1.62" in line for line in lines)
    assert "Specimen slightly hemolyzed; result may be affected." in lines  # comments kept as text
    assert " 01" not in text  # superscript lab codes dropped
    assert "All Rights Reserved" not in text and "private and confidential" not in text


def test_header_row_is_not_emitted_as_text():
    text = parse(fixture_bytes("lab-report-columns.pdf"), ".pdf").pages[0][1]
    assert "Current Result and Flag" not in text


def test_previous_result_word_does_not_create_a_second_current_column():
    words = row(100, HEADER) + row(114, [(36, "BUN"), (198, "12"), (333, "37"), (385, "08/12/2025"),
                                        (460, "mg/dL"), (544, "6-20")])  # fmt: skip
    text, found = page_text(words)
    older = "Older results from 08/12/2025 (not current): BUN 37 mg/dL."
    assert found and text == f"BUN: 12 mg/dL (reference 6-20).\n{older}"


def test_superscript_codes_are_dropped_wherever_they_sort():
    words = row(100, HEADER) + row(
        114, [(36, "Glucose"), (198, "94"), (460, "mg/dL"), (542, "70-99")]
    )
    words.append(Word("01", 67, 112.5, 5.0))  # smaller font, slightly raised
    text, _ = page_text(words)
    assert text == "Glucose: 94 mg/dL (reference 70-99)."


def test_flag_only_rows_and_short_flags():
    words = row(100, HEADER) + row(114, [(36, "Protein/Creat"), (93, "Ratio"), (250, "Abnormal"),
                                        (452, "mg/g"), (473, "creat"), (542, "0-200")])  # fmt: skip
    words += row(128, [(163, "recollection"), (225, "at"), (240, "a"), (249, "time")])
    text, _ = page_text(words)
    lines = text.splitlines()
    assert lines[0] == "Protein/Creat Ratio: no numeric value (reference 0-200), flagged Abnormal."
    assert lines[1] == "recollection at a time"  # a lone "a" is not a flag without a value


def test_pages_without_a_table_keep_their_text():
    # the original fixture has no results header: extraction falls back to pypdf text
    text = parse(fixture_bytes("lab-report.pdf"), ".pdf").pages[1][1]
    assert "LDL cholesterol ......... 162 mg/dL" in text


def test_boilerplate_patterns():
    footers = [
        "©2025 Laboratory Corporation of America® Holdings",
        "All Rights Reserved - Enterprise Report Version 2.00",
        "Date Created and Stored 10/15/25 1613 ET Final Report Page 1 of 2",
        "This document contains private and confidential health information.",
    ]
    for line in footers:
        assert is_boilerplate(line), line
    for line in [
        "Creatinine: 1.06 mg/dL (reference 0.76-1.27).",
        "Reference ranges vary by laboratory.",
    ]:
        assert not is_boilerplate(line), line


def test_ingest_records_extractor_version_and_reindexes_old_documents(tmp_path):
    svc = make_service(tmp_path)
    record = svc.ingest("labs.pdf", None, fixture_bytes("lab-report-columns.pdf")).record
    assert record.extractor_version == EXTRACTOR_VERSION

    # simulate a document indexed before this change: old version, garbage chunk text
    old = record.model_copy(update={"extractor_version": 1, "chunks": 1})
    svc.registry.add(old)
    svc.store.delete_document(record.id)
    from pha.rag.chunker import Chunk

    stale = [Chunk("Creatinine 01 0.98 1.62 03/02/2026 mg/dL 0.76-1.27", 1, 0)]
    svc.store.add(record.id, "labs.pdf", stale, svc.embedder.embed_documents([stale[0].text]))

    svc.reconcile()
    upgraded = svc.registry.get(record.id)
    assert upgraded.extractor_version == EXTRACTOR_VERSION and upgraded.chunks == record.chunks
    hits = svc.retriever.search("older results creatinine previous")
    assert any("Older results from 03/02/2026 (not current)" in h.text for h in hits)
    assert not any("Creatinine 01 0.98 1.62" in h.text for h in hits)
    saved = json.loads((tmp_path / "documents.json").read_text())
    assert saved[0]["extractor_version"] == EXTRACTOR_VERSION


def test_prose_mentioning_previous_result_is_not_a_header():
    prose = "match the result to the patient. Results from certain tests are excluded from the "
    sentence = (prose + "Previous Result display.").split(" ")
    x, cells = 36.0, []
    for w in sentence:
        cells.append((x, w))
        x += 4.5 * len(w) + 3
    text, found = page_text(row(100, cells) + row(114, [(36, "FL,"), (60, "32606"), (198, "4423")]))
    assert not found
    assert "(no reference given)" not in text


def test_older_results_are_history_chunks_retrieved_only_when_asked(tmp_path):
    svc = make_service(tmp_path, min_score=0.0)
    svc.ingest("labs.pdf", None, fixture_bytes("lab-report-columns.pdf"))
    current = svc.retriever.search("What was my creatinine?")
    assert current and not any(h.history or "not current" in h.text for h in current)
    assert any("Creatinine: 0.98 mg/dL" in h.text for h in current)
    previous = svc.retriever.search("What was my previous creatinine result?")
    assert any(h.history and "Creatinine 1.62 mg/dL" in h.text for h in previous)


def test_history_text_is_its_own_block():
    pages = parse(fixture_bytes("lab-report-columns.pdf"), ".pdf").pages
    assert len(pages) == 2 and pages[0][0] == pages[1][0] == 1
    assert pages[1][1].startswith("Older results from 03/02/2026 (not current)")
    assert "Older results" not in pages[0][1]


def test_same_name_tests_are_labelled_by_specimen():
    pages = parse(fixture_bytes("lab-report-renal.pdf"), ".pdf").pages
    current, history = pages[0][1], pages[1][1]
    lines = current.splitlines()
    assert "Creatinine (blood): 1.31 mg/dL (reference 0.76-1.27), flagged High." in lines
    note = next(line for line in lines if line.startswith("This report has 2 different creatinine"))
    assert "blood 1.31 mg/dL" in note and "urine 88.2 mg/dL" in note
    # the note sits right after the first twin, so they land in the same chunk
    assert (
        lines.index(note)
        == lines.index(next(x for x in lines if x.startswith("Creatinine (blood)"))) + 1
    )
    assert "Creatinine (blood) 0.95 mg/dL" in history  # older results carry the label too
    # "Protein, Total, Urine" and "Protein/Creat Ratio" are different tests: no note for them
    assert sum(line.startswith("This report has") for line in lines) == 1
    assert twin_notes(current) == [("creatinine", "blood 1.31 mg/dL; urine 88.2 mg/dL")]


def test_no_labels_without_a_specimen_twin():
    text = parse(fixture_bytes("lab-report-columns.pdf"), ".pdf").pages[0][1]
    assert (
        "Creatinine: 0.98 mg/dL" in text and "(blood)" not in text and "This report has" not in text
    )


def test_urine_heading_sets_the_specimen_of_unlabelled_rows():
    words = row(80, [(36, "Urinalysis")]) + row(100, HEADER)
    words += row(114, [(36, "Creatinine"), (198, "88"), (460, "mg/dL"), (544, "20-300")])
    words += row(140, [(36, "Chemistry")]) + row(160, HEADER)
    words += row(174, [(36, "Creatinine"), (198, "1.1"), (460, "mg/dL"), (544, "0.76-1.27")])
    text, _ = page_text(words)
    assert "Creatinine (urine): 88 mg/dL" in text and "Creatinine (blood): 1.1 mg/dL" in text
    assert "urine 88 mg/dL; blood 1.1 mg/dL" in text


def test_not_established_reference_is_explicit():
    lines = parse(fixture_bytes("lab-report-renal.pdf"), ".pdf").pages[0][1].splitlines()
    urine = next(line for line in lines if line.startswith("Creatinine, Urine"))
    assert urine == "Creatinine, Urine: 88.2 mg/dL. The lab gives no reference range for this test."
