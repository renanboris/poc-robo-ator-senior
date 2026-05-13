# Bugfix Requirements Document

## Introduction

The capture system (`capture_dual_output.py`) is failing to generate stable, semantic CSS selectors for PrimeNG search buttons and modal selection elements in Senior X ERP. When the robot executor (`vision_engine.py`) attempts to replay these captured actions, it cannot resolve the selectors and falls back to coordinate-based clicking, which has a low success rate (~26%). This results in failed automation workflows and requires manual intervention.

The bug affects two critical interaction patterns:
1. **Search buttons** within PrimeNG autocomplete components (e.g., `button.button-addon` with `icon="fa fa-search"`)
2. **Modal selection elements** such as table rows and buttons within PrimeNG dialogs (`p-dialog`, `ui-dialog`)

The root cause is that `resolvePrimeNGComponent()` in the capture script does not properly handle:
- Search buttons that appear within modal dialogs after user interactions
- Table row selections within modal search results
- Dynamic PrimeNG components that render after asynchronous operations

This leads to generic, ambiguous selectors like `'ui-btn'` that match multiple elements, forcing the executor to use unreliable coordinate-based fallback strategies.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the user clicks a search button with `class="button-addon"` and `icon="fa fa-search"` within a PrimeNG autocomplete component inside a modal dialog THEN the system captures a generic selector like `'ui-btn'` that matches multiple elements on the page

1.2 WHEN the user selects a table row within a PrimeNG dialog search result (e.g., selecting "Adiantamento Crédito a Identificar" from a modal list) THEN the system fails to capture any stable selector and the executor cannot locate the element

1.3 WHEN the user clicks a transaction row with a specific code (e.g., "90330") within a modal table THEN the system does not anchor the selector to the modal context and the executor searches the entire DOM, finding multiple ambiguous matches

1.4 WHEN the executor attempts to replay actions with generic selectors like `'ui-btn'` THEN it finds 4+ candidate elements and falls back to coordinate-based clicking with ~26% success rate

1.5 WHEN the executor uses coordinate-based fallback for modal interactions THEN the action fails completely because modal positions are dynamic and viewport-dependent

### Expected Behavior (Correct)

2.1 WHEN the user clicks a search button with `class="button-addon"` and `icon="fa fa-search"` within a PrimeNG autocomplete component inside a modal dialog THEN the system SHALL capture a scoped selector that anchors to the modal context and the input field identifier (e.g., `p-dialog [name='tipoTitulo'] button.button-addon`)

2.2 WHEN the user selects a table row within a PrimeNG dialog search result THEN the system SHALL capture a selector that combines the modal scope with the row's unique text content (e.g., `p-dialog tr:has-text("Adiantamento Crédito a Identificar")`)

2.3 WHEN the user clicks a transaction row with a specific code within a modal table THEN the system SHALL capture a selector scoped to the modal and anchored to the unique text (e.g., `p-dialog tr:has-text("90330")`)

2.4 WHEN the executor attempts to replay actions with modal-scoped selectors THEN it SHALL resolve the element within the dialog context without falling back to coordinate-based clicking

2.5 WHEN the executor uses modal-scoped selectors THEN the action SHALL succeed reliably (>90% success rate) regardless of viewport size or modal position

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user interacts with PrimeNG components outside of modal dialogs (e.g., main form autocomplete fields, calendar triggers, dropdown buttons) THEN the system SHALL CONTINUE TO capture stable selectors using the existing `resolvePrimeNGComponent()` logic

3.2 WHEN the user interacts with checkbox elements in table rows THEN the system SHALL CONTINUE TO use the `:has-text()` strategy to anchor selectors to row content

3.3 WHEN the user interacts with confirmation dialog buttons (e.g., "Sim", "Não", "Confirmar") THEN the system SHALL CONTINUE TO scope selectors to the dialog context using the existing `_SELETORES_DIALOG` patterns in `vision_engine.py`

3.4 WHEN the executor replays actions for non-modal PrimeNG components THEN it SHALL CONTINUE TO use the existing candidate generation and fallback cascade (Brain → Sniper → Coordinates → Vision)

3.5 WHEN the capture system generates selectors for standard HTML elements (buttons, inputs, links) THEN it SHALL CONTINUE TO use the existing `getBestSelector()` fallback logic
