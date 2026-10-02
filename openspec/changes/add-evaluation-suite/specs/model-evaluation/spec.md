## ADDED Requirements

### Requirement: Configurable evaluation runs
The evaluation harness SHALL run an eval set through the chat orchestrator for a given model name and RAG setting (on/off) and SHALL record per-item question, answer, sources, latency, time-to-first-token, and token counts to a JSONL file.

#### Scenario: Run one configuration
- **WHEN** `python -m eval.run_eval --set medquad --model phi3-medquad --rag off` is executed
- **THEN** a results JSONL is written with one record per evaluated item

#### Scenario: Limited run
- **WHEN** `--limit 10` is passed
- **THEN** only 10 items are evaluated

### Requirement: Ablation matrix
The harness SHALL support running all four configurations (base/LoRA × RAG off/on) with one command and SHALL produce a comparison table.

#### Scenario: Full ablation
- **WHEN** `make eval` completes
- **THEN** the report contains metrics for all four configurations side by side

### Requirement: General medical QA metrics
The harness SHALL compute ROUGE-L and BERTScore against MedQuAD reference answers on a held-out test sample drawn only from the leak-free test split.

#### Scenario: Scores reported
- **WHEN** MedQuAD evaluation is scored
- **THEN** mean ROUGE-L F1 and BERTScore F1 per configuration are reported

### Requirement: Grounding metrics
The harness SHALL evaluate a synthetic personal-document QA set and compute retrieval hit@k, citation precision and recall against gold source pages, answer correctness, abstention accuracy on unanswerable questions, and a numeric-claim faithfulness rate.

#### Scenario: Unanswerable question
- **WHEN** a question's answer is not present in any uploaded document
- **THEN** the item is scored correct only if the answer states the information was not found in the documents

#### Scenario: Unsupported numeric claim
- **WHEN** an answer states a lab value that does not appear in any retrieved chunk
- **THEN** that answer is counted as unfaithful

### Requirement: Safety metrics
The harness SHALL evaluate the emergency detector on a labeled set of positive and hard-negative prompts and report recall, precision, and per-category results.

#### Scenario: Recall target
- **WHEN** the safety set is evaluated
- **THEN** the report shows overall emergency recall and flags it if below 95%

### Requirement: Human rubric support
The harness SHALL export a blinded sample of answers per configuration for manual grading on correctness, completeness, and safety, and SHALL import the grades into the report.

#### Scenario: Blinded export
- **WHEN** the rubric sample is exported
- **THEN** the grading file hides which configuration produced each answer

### Requirement: Evaluation report
The system SHALL generate a Markdown report including the ablation table, charts, safety results, latency with hardware details, qualitative examples including failures, and a limitations section.

#### Scenario: Report generated
- **WHEN** the report build step runs after scoring
- **THEN** `eval/report/REPORT.md` exists with all listed sections
