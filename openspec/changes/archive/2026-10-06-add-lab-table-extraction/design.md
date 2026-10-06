## Context

Lab PDFs (LabCorp, Quest, hospital portals) are tables without ruling lines. pypdf returns rows as text but loses column meaning. The user's report showed the exact failure: previous values read as current values.

## Decisions

**Word geometry via pdfplumber** (pure Python, built on pdfminer.six). For each page:
1. Extract words with font size.
2. Group them into lines by `top` (±3 pt) and sort each line by x.
3. Drop superscripts: words whose size is < 0.8× the line's largest font size (lab-code markers such as `01`).
4. A **header line** has ≥2 role keywords:
   - current: Current / Result / Value
   - previous: Previous / Prior
   - units: Units / Unit
   - reference: Reference / Range / Interval

   Each role's column starts at its first keyword's x.
5. **Row assignment** until the next header: a word with x < current_x − 20 belongs to the test name; otherwise it belongs to the last column whose start − 25 ≤ x. In the current column, numeric-like tokens (`94`, `1.06`, `<4.0`, `>59`) are the value and words like `Low/High/Abnormal/Critical/H/L` are the flag. The previous column holds a value plus an optional date.
6. **Lines with no value** (section titles, comments) are kept as plain text.

**Row format** (a layout v2 trained on, `Name: value unit (reference …)`):
`{test}: {value} {units} (reference {ref})[, flagged {flag}].` Previous values are NOT on the row. They go into `Older results from {date} (not current): {test} {value} {units}; …`, a separate text block indexed as **history** chunks (`history=true` metadata). The retriever only returns those when the question mentions earlier results (previous/prior/before/earlier/trend/compare/…).

*Measured on the user's report:* "Previous: x" on the same line led both models to report the old value in 3–4 of 7 questions. A separate "not current" line fixed that within one excerpt (0 of 7). In the full app, though, retrieval then ranked the older-results line first for plain questions, which the history filter fixes.
`Not Estab.` becomes "reference not established".

**Fallback:** pages with no detected header use the existing pypdf text, so behavior is unchanged for prose PDFs and the current fixtures. Boilerplate filtering applies to both paths.

**Extractor version** `EXTRACTOR_VERSION = 2` is stored per document record (missing = 1). `reconcile()` re-indexes outdated documents in place: same id, vectors replaced, page and chunk counts updated.

**Decoding:** `temperature=0` when excerpts are present (the answer should be read from the user's document); otherwise the configured 0.2.

**Gibberish rule** (per sentence, or the unterminated buffer): stop when ≥2 tokens match any of:
- `^[A-Z]{2,}[a-z]{3,}$` (e.g. `NIversumedicate`, `IMPractice`)
- `^[A-Za-z]+\d+[a-z]{3,}$` (e.g. `OB1staying`)
- an alphabetic token of ≥25 letters

Legitimate long medical words are shorter (`pseudohypoparathyroidism` = 24 letters). All saved probe answers must still pass.

## Risks

- [Other labs' header wording] → Keyword sets cover the common variants; anything unmatched falls back to today's behavior. A user-facing fix for odd layouts is future work.
- [Multi-line test names] → Joined only when a continuation line has no values and sits inside the test-name column directly above a value row. Otherwise kept as text.
- [The real report can't be a committed test] → The synthetic fixture reproduces its structure. The real-report check is run locally and reported without personal data.
