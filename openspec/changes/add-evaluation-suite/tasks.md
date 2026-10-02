## 1. Eval sets

- [ ] 1.1 Sample ~200 MedQuAD test items stratified by question type into `eval/sets/medquad.jsonl`
- [ ] 1.2 Author ~40 doc-QA items over fictional fixture documents with gold answers, gold (filename, page), including unanswerables and distractors
- [ ] 1.3 Author ~40 emergency positives across categories and ~20 hard negatives in `eval/sets/safety.jsonl`

## 2. Harness

- [ ] 2.1 Implement `eval/run_eval.py` invoking the orchestrator in-process with `--set`, `--model`, `--rag`, `--limit`, output JSONL
- [ ] 2.2 Implement fixture loading for doc-QA runs (fresh temp Chroma + uploads per run)
- [ ] 2.3 Add `make eval` running the 2×2 ablation with output caching

## 3. Metrics

- [ ] 3.1 Implement ROUGE-L and BERTScore scoring with locally cached scorer model
- [ ] 3.2 Implement retrieval hit@k, citation precision/recall, answer correctness, abstention accuracy
- [ ] 3.3 Implement numeric-claim faithfulness heuristic (values with units must appear in retrieved chunks)
- [ ] 3.4 Implement safety recall/precision per category with ≥95% recall flag
- [ ] 3.5 Implement latency aggregation (TTFT, tokens/s) with hardware info capture
- [ ] 3.6 Implement blinded rubric export and grade import

## 4. Privacy verification

- [ ] 4.1 Add `PHA_NET_GUARD=1` startup hook in backend that patches socket connect to block and log non-loopback targets
- [ ] 4.2 Write E2E pytest: launch backend subprocess with guard, upload → chat → delete, assert empty guard log and no residue
- [ ] 4.3 Add a deliberate-telemetry negative test proving the guard catches an outbound attempt

## 5. Report

- [ ] 5.1 Implement `eval/report/build_report.py` producing `REPORT.md` with ablation table, charts, safety confusion matrix, latency, examples, limitations
- [ ] 5.2 Run full evaluation, complete human rubric grading, and generate the final report
- [ ] 5.3 Link the report and key findings from the README for the showcase
