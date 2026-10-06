# uf-theme Specification

## Purpose
UF Gator look and feel (orange and blue palette, typography, bundled assets) with no affiliation or endorsement implied.

## Requirements
### Requirement: UF color palette
The UI SHALL define design tokens for UF Orange (`#FA4616`) and UF Blue (`#0021A5`) and use them as the primary accent and primary surface colors respectively.

#### Scenario: Header and primary actions
- **WHEN** the app is rendered
- **THEN** the header background uses UF Blue and the primary Send button uses UF Orange

### Requirement: Accessible contrast
All text SHALL meet WCAG 2.1 AA contrast; UF Orange SHALL NOT be used for body-size text on white backgrounds.

#### Scenario: Automated accessibility check
- **WHEN** an axe accessibility scan runs against the main screen
- **THEN** it reports no color-contrast violations

### Requirement: Original mascot and no official marks
The UI SHALL use an original gator illustration and SHALL NOT include official University of Florida logos or wordmarks, and SHALL include a footer note that the project is a student capstone not endorsed by UF or UF Health.

#### Scenario: Footer notice
- **WHEN** the app is rendered
- **THEN** the footer contains the non-affiliation notice

### Requirement: Self-hosted assets
Fonts, icons, and images SHALL be bundled with the frontend build and SHALL NOT be loaded from remote origins.

#### Scenario: Offline rendering
- **WHEN** the app is loaded with the network disconnected
- **THEN** the font, mascot, and icons render correctly

### Requirement: Responsive layout
The UI SHALL support viewports from 360px to desktop widths, collapsing the documents panel into a drawer below 768px.

#### Scenario: Mobile width
- **WHEN** the viewport is 375px wide
- **THEN** the chat occupies the full width and the documents panel is accessible via a toggle

