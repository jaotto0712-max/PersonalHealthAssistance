## Why

The evaluation suite (`eval/report/REPORT.md`) left two record failures for `phi3-medquad-v2`, both
also seen on a real commercial lab report:

- **Same-name tests:** asked "What was my creatinine?", the model gave the blood value (1.31 mg/dL)
  without saying the report also lists a urine creatinine (88.2 mg/dL). The blood line is just
  "Creatinine"; nothing on it says that a second creatinine exists.
- **"Not established" references:** the extracted "(reference not established)" was read as a
  range, and the model answered "within the reference range (not established)".

## What Changes

- Results whose names differ only by specimen (blood or urine) are labelled with their specimen,
  and the page gets one note line listing both, for example "This report has two creatinine
  results: blood 1.31 mg/dL; urine 88.2 mg/dL. Say which one you mean if it matters."
- A "not established" reference is written as its own sentence, "The lab gives no reference range
  for this test, so it is not rated high or low.", not inside the "(reference …)" slot.
- The chat adds a note when the question names such a test without saying blood or urine, for
  example "Note: your report has more than one creatinine result (blood 1.31 mg/dL; urine
  88.2 mg/dL)…". A wording probe (4 variants × 2 models on the 8 renal questions) showed that
  no extraction wording made `phi3-medquad-v2` mention both values: it answers record questions
  with a fixed, learned template. So the app states it, like the existing "couldn't find" notice.
- `EXTRACTOR_VERSION` 4 → 5, so stored documents are re-indexed on startup.

Not fixed here: v2 still writes "within the reference range" for a test with no range. That
comes from its training template and needs v3 training data.

Prompts and the model are unchanged (prompt parity with training is untouched).

## Impact

- Code: `backend/pha/rag/lab_tables.py`, `backend/pha/rag/parsers.py`, `backend/pha/chat/orchestrator.py`.
- Tests: `backend/tests/test_lab_tables.py`, `backend/tests/test_orchestrator.py`, `eval/tests/test_scoring.py`.
- Measured by re-running the `records` set for all three models.
