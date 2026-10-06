# medquad-dataset-prep Specification

## Purpose
Deterministic download, cleaning and topic-level splitting of MedQuAD into training, validation and test sets.

## Requirements
### Requirement: MedQuAD ingestion
The data preparation script SHALL parse MedQuAD source files into records containing question, answer, focus, question type, and source collection, and SHALL exclude records with missing or empty answers.

#### Scenario: Records with removed answers are excluded
- **WHEN** the script processes a MedQuAD subset whose answers were removed
- **THEN** none of those records appear in the output

### Requirement: Cleaning and deduplication
The script SHALL normalize whitespace, strip markup, drop exact duplicate question–answer pairs, and drop answers shorter than a configurable minimum length.

#### Scenario: Duplicate pair removed
- **WHEN** two records have identical normalized question and answer text
- **THEN** only one appears in the output

### Requirement: Leak-free split
The script SHALL split data into train, validation, and test sets (default 80/10/10) grouped by question focus, using a fixed seed, so that no focus appears in more than one split.

#### Scenario: No focus overlap
- **WHEN** the splits are produced
- **THEN** the set of focus values in test has an empty intersection with the focus values in train and in validation

#### Scenario: Reproducible split
- **WHEN** the script is run twice with the same seed and input
- **THEN** the output files are byte-identical

### Requirement: Chat-formatted output
The script SHALL write each split as JSONL where each line contains `messages` (system, user, assistant) using the same system prompt as inference, plus the original metadata fields.

#### Scenario: Valid chat record
- **WHEN** a line from `train.jsonl` is parsed
- **THEN** it contains a `messages` array with roles `system`, `user`, `assistant` in that order

### Requirement: Dataset statistics
The script SHALL emit a summary of record counts per split, per source collection, and answer-length distribution.

#### Scenario: Stats file written
- **WHEN** preparation completes
- **THEN** a `stats.json` file exists alongside the splits with counts for each split

