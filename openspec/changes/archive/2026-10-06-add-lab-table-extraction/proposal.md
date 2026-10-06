## Why

On the user's real LabCorp report (uploaded locally, never committed), the app answered 3 of 6 lab questions cleanly. It reported a **previous** creatinine (1.94) as the current one (1.06), said "I couldn't find any hemoglobin results" while citing the hemoglobin row, and ended one answer in word salad that borrowed the report's legal footer. Causes:
- Plain-text PDF extraction drops columns: `Creatinine 01 1.06 1.94 08/12/2025 mg/dL 0.76-1.27` has a lab code, the current value and the previous value, with nothing saying which is which.
- Report boilerplate (copyright, confidentiality notices, page footers) is indexed and retrieved.
- The degeneration guard catches loops, but not gibberish with punctuation.

## What Changes

- **Column-aware lab tables in PDFs** (pdfplumber word positions): detect a table header (current/result/value, previous/prior, units, reference/range/interval), assign each word to a column by x-position, and drop superscript footnote markers (lab codes). Each row becomes one self-describing line: `Creatinine: 1.06 mg/dL (reference 0.76-1.27). Previous: 1.94 mg/dL on 08/12/2025.` Flags become `flagged Low`. Pages without a recognizable table keep the existing extraction.
- **Boilerplate filter** for copyright/rights lines, "Page x of y", confidentiality notices, report-version and "date created" footers.
- **Automatic re-indexing:** documents record an extractor version; on startup, documents from an older extractor are re-parsed from their stored file and re-indexed.
- **Synthetic column-layout fixture** `eval/fixtures/docs/lab-report-columns.pdf` (fictional patient; current and previous columns, superscript lab codes, flags, comment lines, footer) and matching grounding-probe questions.
- **Safer grounded decoding:** temperature 0 when answering from retrieved excerpts (deterministic extraction). The guard also stops gibberish: two or more malformed words (mixed-case fusions like `NIversumedicate`, letter-digit fusions like `OB1staying`, runs of ≥25 letters) within one sentence.

## Capabilities

### New Capabilities
- `lab-table-extraction`: Column-aware extraction of lab result tables and removal of report boilerplate, with re-indexing on extractor upgrades.
- `generation-safety-v2`: Deterministic grounded decoding and gibberish detection.

## Impact

- Backend: `pha/rag/parsers.py`, `pha/rag/service.py` and registry (extractor version, reindex), `pha/chat/guard.py`, `pha/chat/orchestrator.py`. New dependency: `pdfplumber`.
- Fixtures: `eval/fixtures/make_fixtures.py` (positioned-text PDF writer) and a new fixture; `training/grounding_probe.py` probes.
