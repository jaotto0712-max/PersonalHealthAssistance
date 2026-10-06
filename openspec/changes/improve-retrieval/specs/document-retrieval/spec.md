## ADDED Requirements

### Requirement: Follow-up questions use conversation context
When a message refers back to the conversation (for example "it", "that", "last time") and a previous user message exists, retrieval SHALL also search with the previous user message and SHALL merge both result lists by score.

#### Scenario: Follow-up about a previous result
- **WHEN** the user asked "What was my BUN?" and then asks "What was it last time?"
- **THEN** retrieval returns the excerpt with the BUN results

#### Scenario: New topic
- **WHEN** the user asks a self-contained question with no reference words
- **THEN** only that question is searched

### Requirement: Keyword matching complements embeddings
Retrieval SHALL combine keyword (BM25) ranking with vector ranking, and every returned excerpt SHALL still meet the minimum similarity score.

#### Scenario: Exact short test name
- **WHEN** the user asks "What was my BUN?" and a document contains a BUN result
- **THEN** that excerpt is among the results
