## 1. Extraction

- [x] 1.1 Add pdfplumber; column-aware table extraction with superscript removal, flags, previous values, notes
- [x] 1.2 Boilerplate filter (both paths); fallback to pypdf for pages without a table header
- [x] 1.3 Synthetic column-layout fixture via positioned-text PDF writer; extraction unit tests
- [x] 1.4 Extractor version on records; reconcile re-indexes outdated documents; tests

## 2. Generation safety

- [x] 2.1 Temperature 0 for grounded requests; test
- [x] 2.2 Gibberish rule in the guard; tests (incl. all saved probe answers pass)

## 3. Verify

- [x] 3.1 Grounding probe gains column-layout questions (current vs previous); run base and v2 → both 5/5 on column probes; v2 overall 16/16 value, 12/12 direction, 16/16 citation, 3/3 absence (`training/results/grounding_probe_v3.json`)
- [x] 3.2 Local check on the user's uploaded report (re-indexed automatically to extractor v4): 10/11 correct, up from 3/6 clean before. Two measured design changes along the way:
  - **Older results moved off the result rows** into "Older results … (not current)" lines. With "Previous: x" on the same line, the models reported the old value in 3–4 of 7 questions; with the separate line, 0 of 7 (both models).
  - **Older results indexed as separate history chunks**, retrieved only when the question asks about earlier results. In the full app, search otherwise ranked that line first.

  Remaining miss: "What was my creatinine?" with two creatinines on the report (blood and urine). The urine row ranked first and was answered. This is a genuine ambiguity, logged as a limitation.
