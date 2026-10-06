## ADDED Requirements

### Requirement: Pipeline evaluation runs
The harness SHALL run evaluation sets through the real chat pipeline for each requested model and retrieval setting, and SHALL record per item: answer, cited sources, retrieved count, guard outcome, time to first token, tokens per second, and scores.

#### Scenario: Run a configuration
- **WHEN** `python -m eval.run_eval --sets records --models phi3-medquad-v2 --rag on` runs
- **THEN** a results JSONL contains one scored record per item

#### Scenario: Cached re-run
- **WHEN** the same command runs again without changes to prompts, extractor or model
- **THEN** cached items are reused and no model calls are made for them

### Requirement: Failure-category record questions
The records set SHALL tag each question with one of: value, direction, current_vs_previous, same_name_ambiguity, absent, followup, no_documents, citation. Accuracy SHALL be reported per category and model.

#### Scenario: Previous value reported as current
- **WHEN** an answer's first stated value is the item's previous value
- **THEN** the item fails and counts toward the previous-as-current rate

#### Scenario: Ambiguous test name
- **WHEN** a question names a test that appears twice (blood and urine)
- **THEN** the item passes only if both values are given or the answer asks which one is meant

### Requirement: Closed-book knowledge metrics
The harness SHALL score held-out MedQuAD answers by ROUGE-L F1 and by embedding cosine similarity with the local embedding model.

#### Scenario: Scores reported
- **WHEN** the medquad set is evaluated
- **THEN** mean ROUGE-L and mean similarity are reported per model

### Requirement: Output-quality metrics
The harness SHALL report, per model, guard stops by reason, leaked template tokens, and median answer length.

#### Scenario: Guard stop counted
- **WHEN** the degeneration guard stops an answer
- **THEN** the report counts it under its reason

### Requirement: Safety metrics
The harness SHALL report emergency-detector recall and precision per category, flag recall below 95%, and verify that emergencies never call the model.

#### Scenario: Short-circuit verified
- **WHEN** an emergency question runs through the pipeline
- **THEN** the model backend receives no request

### Requirement: Evaluation report
The system SHALL generate `eval/report/REPORT.md` with per-set tables across models and retrieval settings, per-category accuracy, output-quality and latency tables, the worst examples with raw answers, environment details, and limitations.

#### Scenario: Report generated
- **WHEN** `make eval` completes
- **THEN** the report exists and includes every evaluated configuration
