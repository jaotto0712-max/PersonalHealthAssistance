## ADDED Requirements

### Requirement: Same-name tests are disambiguated
When a lab report lists results whose names differ only by specimen (for example blood and urine creatinine), the extractor SHALL label each result with its specimen and SHALL add one note line naming every such result with its value.

#### Scenario: Blood and urine creatinine on one report
- **WHEN** a report lists "Creatinine 1.31 mg/dL" in a blood panel and "Creatinine, Urine 88.2 mg/dL"
- **THEN** the extracted text labels them as blood and urine creatinine
- **AND** contains a note listing both values

#### Scenario: No false twins
- **WHEN** names share a word but measure different things (for example "Protein, Total, Urine" and "Protein/Creat Ratio")
- **THEN** no note line is added for them

### Requirement: Explicit missing reference range
When a result's reference is "not established", the extracted line SHALL state, in a sentence of its own rather than in the reference slot, that the lab gives no reference range and that the value is not rated high or low.

#### Scenario: Not-established reference
- **WHEN** a row's reference column reads "Not Estab."
- **THEN** its line ends with "The lab gives no reference range for this test, so it is not rated high or low."

### Requirement: Same-name notice in answers
When retrieved excerpts include a same-name note and the user's question names that test without saying blood or urine, the chat SHALL append a note listing every such result with its value.

#### Scenario: Ambiguous creatinine question
- **WHEN** the user asks "What was my creatinine?" about a report with blood and urine creatinine
- **THEN** the answer ends with a note naming both results and their values

#### Scenario: Specific question
- **WHEN** the user asks "What was my urine creatinine?"
- **THEN** no note is added
