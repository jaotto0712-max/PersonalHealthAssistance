## ADDED Requirements

### Requirement: Template cleaning
With `--clean-templates`, data preparation SHALL drop resource-list answers and Human Phenotype Ontology symptom-table answers, SHALL strip a leading restated question from answers when the remainder meets the minimum length, and SHALL report each count in `stats.json`.

#### Scenario: Boilerplate removed
- **WHEN** preparation runs with `--clean-templates`
- **THEN** no output answer starts with "These resources address the diagnosis or management" or contains "Human Phenotype Ontology provides the following list"

#### Scenario: Echoed question stripped
- **WHEN** an answer is "What causes X? X is caused by …"
- **THEN** the output answer is "X is caused by …"

### Requirement: RAFT-style grounded examples
With `--grounded`, each prepared MedQuAD record SHALL be rendered, deterministically by seed, as closed-book, oracle, or distractor-only in the app's prompt format. Distractors SHALL come from other focus groups in the same split.

#### Scenario: Oracle example
- **WHEN** a record is rendered as an oracle example
- **THEN** its system message contains the RAG instructions and numbered excerpts including the gold passage, and its target cites the gold excerpt numbers as `[n]`

#### Scenario: Distractor-only example
- **WHEN** a record is rendered as distractor-only
- **THEN** none of its excerpts contain the gold passage and its target begins by stating the information was not found in the documents

#### Scenario: No cross-split leakage
- **WHEN** grounded splits are produced
- **THEN** every excerpt in a split comes from records of that same split

### Requirement: Synthetic personal-record examples
The generator SHALL produce fictional lab, medication and visit documents in multiple layouts, with questions whose targets state the exact value, the reference range, the correct high/low/normal direction and a citation, or state that the item is not in the documents.

#### Scenario: Correct direction
- **WHEN** a lab value is above its reference range
- **THEN** the target answer describes it as above the range and never as normal or desirable

#### Scenario: Absent item
- **WHEN** a question asks about an analyte not present in any provided document
- **THEN** the target states it could not be found in the documents and cites nothing

#### Scenario: Fictional data only
- **WHEN** records are generated
- **THEN** every document is marked synthetic and uses generated patient names, none matching the evaluation fixtures

### Requirement: Grounding probe
`training/grounding_probe.py` SHALL score any Ollama model on fixed record questions with known answers, reporting exact-value accuracy, direction accuracy, citation rate and correct-absence rate.

#### Scenario: Compare models
- **WHEN** the probe runs against `phi3-base` and `phi3-medquad-v2`
- **THEN** it prints one row per model with the four rates
