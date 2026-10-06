# generation-guards Specification

## Purpose
Stop degenerate output (loops, word salad, gibberish) while streaming, and decode grounded answers deterministically.

## Requirements
### Requirement: Degeneration stop
The chat orchestrator SHALL stream model output in complete sentences and SHALL stop generation, without emitting the offending text, when a normalized sentence of five or more words repeats an earlier one, when the same five-word sentence opener occurs five times, or when forty or more consecutive words arrive without punctuation. A stopped answer SHALL end with a short note and the `done` event SHALL include `stopped_early: true` and the reason.

#### Scenario: Repeated paragraph
- **WHEN** the model emits the same sentence a second time
- **THEN** the repeated sentence is not sent to the client, generation is cancelled, and the answer ends with the stopped note

#### Scenario: Word salad
- **WHEN** the model emits forty or more words in a row without punctuation
- **THEN** that run is not sent to the client and generation stops

#### Scenario: Normal answer unaffected
- **WHEN** the model emits a normal multi-sentence answer
- **THEN** the client receives exactly the model's text and `stopped_early` is false

### Requirement: Personal-question notice
When retrieval returns no excerpts for a first-person question (e.g. "my", "do I", "am I"), the answer SHALL begin with a fixed sentence before the model's text. The sentence states that no documents are uploaded if the document store is empty; otherwise it states that nothing relevant was found in the user's documents.

#### Scenario: No documents uploaded
- **WHEN** the store is empty and the user asks "What does my cholesterol result mean?"
- **THEN** the answer begins with "You haven't uploaded any documents yet, so I can't see your health records."

#### Scenario: General question
- **WHEN** the user asks "How do vaccines work?" and nothing is retrieved
- **THEN** no notice is added

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
