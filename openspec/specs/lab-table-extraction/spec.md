# lab-table-extraction Specification

## Purpose
Read column-layout lab reports into clear current-result lines and separate older-result history chunks.

## Requirements
### Requirement: Column-aware lab tables
For PDF pages containing a lab table header, extraction SHALL output one line per result row stating the test name, the current value with units, the reference interval, any flag, and any previous value with its date, each explicitly labelled.

#### Scenario: Current versus previous
- **WHEN** a row has current value 1.06 and previous value 1.94 dated 08/12/2025
- **THEN** the extracted line states the current value as 1.06 and labels 1.94 as "Previous … on 08/12/2025"

#### Scenario: Superscript lab code removed
- **WHEN** a row contains a smaller raised footnote marker such as `01`
- **THEN** the marker does not appear in the extracted line

#### Scenario: Flag preserved
- **WHEN** a row's current column contains "12.1 Low"
- **THEN** the line includes the value 12.1 and "flagged Low"

#### Scenario: Pages without tables unchanged
- **WHEN** a PDF page has no recognizable lab table header
- **THEN** its extracted text is the same as before this change, apart from boilerplate removal

### Requirement: Boilerplate removal
Extraction SHALL drop report boilerplate lines (copyright and rights notices, "Page x of y", confidentiality notices, report-version and creation-timestamp footers).

#### Scenario: Footer dropped
- **WHEN** a page ends with "©2025 … All Rights Reserved" and "Page 1 of 2"
- **THEN** neither line is in the indexed text

### Requirement: Re-index on extractor upgrade
Each document SHALL record the extractor version used. At startup, documents indexed with an older version SHALL be re-parsed from their stored file and re-indexed under the same id.

#### Scenario: Existing upload upgraded
- **WHEN** the app starts with a document indexed by extractor version 1
- **THEN** its chunks are replaced with version-2 extraction and its record shows version 2

