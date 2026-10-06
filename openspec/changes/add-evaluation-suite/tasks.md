## 1. Sets and fixtures

- [x] 1.1 Fixture `lab-report-renal.pdf` (blood + urine creatinine, previous results, Not Estab.) in make_fixtures
- [x] 1.2 `eval/sets/records.jsonl`: ~45 categorized questions over the fixtures (value, direction, current_vs_previous, same_name_ambiguity, absent, followup, no_documents, citation)
- [x] 1.3 `eval/sets/medquad.jsonl`: 200 stratified held-out items (seeded) with attribution
- [x] 1.4 `eval/sets/safety.jsonl`: emergency positives and hard negatives

## 2. Harness

- [x] 2.1 `eval/pipeline.py`: build orchestrator per (model, rag) over a temp store with all fixtures; empty store for no_documents
- [x] 2.2 `eval/run_eval.py`: CLI (sets, models, rag, limit, fresh), per-item JSONL, cache keyed by pipeline fingerprint
- [x] 2.3 `make eval` (default: 3 models × rag on/off for records; closed-book medquad; safety)

## 3. Metrics

- [x] 3.1 Records scorers (value, not_values, cite, direction, absent, ambiguous) with unit tests from real answers
- [x] 3.2 ROUGE-L and embedding similarity for medquad
- [x] 3.3 Output quality (guard stops by reason, leaks, length) and latency aggregation
- [x] 3.4 Safety recall/precision per category; short-circuit check

## 4. Report and run

- [x] 4.1 `eval/report.py` → `eval/report/REPORT.md` (tables, per-category, worst examples, environment, limitations)
- [x] 4.2 Run the full evaluation; commit the report; link findings from README and model card

## 5. Privacy verification

- [x] 5.1 `PHA_NET_GUARD=1` startup hook blocking and logging non-loopback connections
- [x] 5.2 E2E test: backend subprocess with guard, upload → chat → delete; empty guard log, no residue
- [x] 5.3 Negative test proving the guard catches an outbound attempt
