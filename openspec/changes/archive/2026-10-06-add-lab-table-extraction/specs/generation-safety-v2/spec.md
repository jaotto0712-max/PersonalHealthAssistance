## ADDED Requirements

### Requirement: Deterministic grounded decoding
When retrieved excerpts are included in the prompt, generation SHALL use temperature 0.

#### Scenario: Grounded request
- **WHEN** a question retrieves at least one excerpt
- **THEN** the model request's temperature option is 0

### Requirement: Gibberish stop
The degeneration guard SHALL stop generation when a sentence contains two or more malformed tokens (mixed-case fusions, letter-digit fusions, or alphabetic runs of 25+ letters), without showing that sentence.

#### Scenario: Word salad with punctuation
- **WHEN** the model emits "All Rights Rxinformation. Medicate OB1staying advice and IMPractice your health."
- **THEN** that sentence is not shown and the answer ends with the stopped note

#### Scenario: Medical vocabulary allowed
- **WHEN** an answer mentions "pseudohypoparathyroidism" or "HbA1c"
- **THEN** the guard does not stop
