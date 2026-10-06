# safety-guardrails Specification

## Purpose
Rule-based emergency and crisis detection that answers with 911/988 guidance without calling the model, plus the medical disclaimer.

## Requirements
### Requirement: Emergency detection
The system SHALL check each user message against emergency and crisis patterns (including chest pain, difficulty breathing, stroke signs, severe bleeding, anaphylaxis, overdose or poisoning, seizure, loss of consciousness, suicidal ideation or self-harm) before any retrieval or generation.

#### Scenario: Cardiac emergency
- **WHEN** a user writes "I have crushing chest pain and my left arm is numb"
- **THEN** the system does not call the model and responds with guidance to call 911 or go to the nearest emergency room, flagged `emergency: true` with category `cardiac`

#### Scenario: Self-harm crisis
- **WHEN** a user writes "I want to end my life"
- **THEN** the system does not call the model and responds with guidance to call or text 988 and to call 911 if in immediate danger, flagged with category `self_harm`

#### Scenario: Negated mention
- **WHEN** a user writes "I had no chest pain during my stress test, what does the report mean?"
- **THEN** the message is not flagged as an emergency

### Requirement: Mandatory disclaimer
Every chat response SHALL include a disclaimer stating the assistant provides general information, is not a substitute for professional medical advice, and that emergencies require calling 911.

#### Scenario: Disclaimer on normal answer
- **WHEN** a chat response completes
- **THEN** the final event includes the disclaimer text

### Requirement: No diagnosis or prescribing persona
The system prompt SHALL instruct the model not to provide diagnoses or prescribe or change medications, and to recommend consulting a clinician for personal medical decisions.

#### Scenario: Medication change request
- **WHEN** a user asks "should I stop taking my metformin?"
- **THEN** the system prompt in effect contains the instruction to defer medication changes to a clinician

