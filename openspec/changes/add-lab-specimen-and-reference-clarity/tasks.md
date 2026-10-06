## 1. Extraction

- [x] 1.1 Structured result rows (name, value, units, specimen) instead of preformatted strings
- [x] 1.2 Specimen detection (urine/urinary vs blood/serum/plasma; unlabelled = blood only when a urine twin exists) and the "two results" note line
- [x] 1.3 "Not established" reference as a separate sentence (chosen by a 4-variant wording probe)
- [x] 1.4 `EXTRACTOR_VERSION` = 5

## 2. Chat

- [x] 2.1 Same-name notice when the question names the test without a specimen

## 3. Verification

- [x] 3.1 Unit tests on the renal fixture and on synthetic rows (no false twins: "Protein, Total, Urine" vs "Protein/Creat Ratio")
- [x] 3.2 Ambiguity scorer requires each value to be attributed to the asked-about test (a mislabelled answer had passed)
- [x] 3.3 Re-run `records` for all three models; report before/after per category
