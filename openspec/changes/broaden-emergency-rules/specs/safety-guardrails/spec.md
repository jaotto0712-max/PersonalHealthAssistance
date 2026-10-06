## ADDED Requirements

### Requirement: Indirect crisis phrasing is detected
Emergency detection SHALL recognise indirect self-harm and suicidal intent (for example "cutting myself", "want to end it", "taking all my pills to end it") and SHALL NOT treat ordinary dosing questions (for example "should I take all my pills at once in the morning?") as emergencies.

#### Scenario: Indirect intent
- **WHEN** the user writes "I'm thinking of taking all my pills to end it"
- **THEN** the self-harm crisis message is shown and the model is not called

#### Scenario: Dosing question
- **WHEN** the user asks "should I take all my pills at once in the morning?"
- **THEN** no emergency is detected
