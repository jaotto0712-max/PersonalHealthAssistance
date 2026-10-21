## ADDED Requirements

### Requirement: Multi-turn grounded examples
The training data SHALL include synthetic conversations where the final question depends on an earlier turn, rendered in the app's exact message order (system with excerpts, earlier user and assistant turns, new question), and SHALL include topic switches where the final question is self-contained.

#### Scenario: Follow-up about a previous result
- **WHEN** the earlier turn asked for a lab value and the final question is "What was it last time?"
- **THEN** the target answer states the older value from the history excerpt with its date and citation, or says no earlier result is listed

### Requirement: App extraction format in training documents
Synthetic lab documents SHALL include the app's extracted line format, older-results blocks and tests with no reference range.

#### Scenario: Test with no reference range
- **WHEN** a synthetic question asks whether a no-range test is normal
- **THEN** the target answer states the value, says the lab gives no reference range, and makes no high or low claim
