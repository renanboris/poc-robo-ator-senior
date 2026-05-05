# DAP Like/Dislike Icons Bugfix Design

## Overview

The like/dislike feedback buttons in the Aura DAP extension display incorrect SVG icons due to a conflict between filled SVG paths with `fill="currentColor"` and CSS rules that enforce `fill: none !important` and `stroke: currentColor !important`. The fix requires replacing the current filled SVG icons with stroke-based outline icons that are compatible with the existing CSS styling system.

## Glossary

- **Bug_Condition (C)**: The condition where SVG icons have `fill="currentColor"` attribute that conflicts with CSS `fill: none !important` rule
- **Property (P)**: The desired behavior where stroke-based SVG icons render correctly with CSS `stroke: currentColor` and `fill: none` styles
- **Preservation**: Existing button functionality (click handlers, hover effects, accessibility, DOM manipulation) that must remain unchanged
- **AuraFeedback.criar()**: The function in `extension/modules/aura_feedback.js` that creates feedback buttons with SVG icons
- **currentColor**: CSS value that inherits the current text color, used for dynamic theming

## Bug Details

### Bug Condition

The bug manifests when the feedback buttons are rendered with filled SVG icons that have `fill="currentColor"` attributes, which conflict with the CSS rule `fill: none !important`. This causes the icons to appear as unrecognizable "capybara" shapes instead of proper thumbs up/down icons.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type HTMLElement (SVG element)
  OUTPUT: boolean
  
  RETURN input.hasAttribute('fill')
         AND input.getAttribute('fill') === 'currentColor'
         AND window.getComputedStyle(input).fill === 'none'
         AND input.parentElement.classList.contains('aura-fb-btn')
END FUNCTION
```

### Examples

- **Like Button**: Current filled thumbs-up SVG with complex path renders as unrecognizable shape when `fill: none` is applied
- **Dislike Button**: Current filled thumbs-down SVG with complex path renders as unrecognizable shape when `fill: none` is applied
- **CSS Conflict**: `fill="currentColor"` attribute is overridden by `fill: none !important` CSS rule
- **Expected Result**: Clean outline thumbs up/down icons that work with stroke-based rendering

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Button click functionality must continue to register feedback and disable buttons after voting
- Hover effects with color changes and transform animations must continue to work
- Voted state styling (voted-yes/voted-no classes) must continue to apply correct colors
- Accessibility attributes (aria-label, title) must remain intact
- DOM manipulation, opacity transitions, and cleanup behavior must remain unchanged

**Scope:**
All functionality that does NOT involve the SVG icon rendering should be completely unaffected by this fix. This includes:
- Event listeners and click handlers
- CSS transitions and hover states
- Button state management (enabled/disabled)
- LocalStorage feedback recording
- DOM creation and removal timing

## Hypothesized Root Cause

Based on the bug analysis, the root cause is:

1. **SVG Icon Type Mismatch**: The current SVG icons are designed for filled rendering with complex paths that don't work well as outlines
   - Like icon uses a complex filled path that becomes unrecognizable when only stroked
   - Dislike icon uses a complex filled path that becomes unrecognizable when only stroked

2. **CSS-JavaScript Attribute Conflict**: The JavaScript sets `fill="currentColor"` but CSS enforces `fill: none !important`
   - CSS rule `fill: none !important` overrides the SVG `fill` attribute
   - CSS expects `stroke: currentColor` for icon rendering
   - Current SVG paths are not optimized for stroke-only rendering

3. **Icon Design Incompatibility**: The current icon paths are sourced from a filled icon set rather than a stroke/outline icon set
   - Filled icons have different path structures than stroke icons
   - Stroke icons typically have simpler, cleaner paths designed for outline rendering

## Correctness Properties

Property 1: Bug Condition - Stroke-Based Icon Rendering

_For any_ SVG icon in a feedback button where stroke-based CSS is applied, the fixed icons SHALL render as recognizable thumbs up/down symbols using stroke-only rendering without fill attributes.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Button Functionality

_For any_ user interaction that is NOT related to SVG icon rendering (clicks, hovers, keyboard navigation), the fixed implementation SHALL produce exactly the same behavior as the original implementation, preserving all button functionality and styling.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

**File**: `extension/modules/aura_feedback.js`

**Function**: `criar()`

**Specific Changes**:
1. **Replace Like Icon SVG**: Replace the current filled thumbs-up path with a stroke-optimized outline version
   - Remove `fill="currentColor"` attribute from SVG element
   - Use simpler path designed for stroke rendering
   - Maintain same viewBox and dimensions (24x24)

2. **Replace Dislike Icon SVG**: Replace the current filled thumbs-down path with a stroke-optimized outline version
   - Remove `fill="currentColor"` attribute from SVG element
   - Use simpler path designed for stroke rendering
   - Maintain same viewBox and dimensions (24x24)

3. **SVG Attribute Cleanup**: Ensure SVG elements only have stroke-compatible attributes
   - Remove all `fill` attributes from SVG and path elements
   - Keep `stroke-width`, `stroke-linecap`, and `stroke-linejoin` attributes if needed
   - Maintain `aria-hidden="true"` for accessibility

4. **Path Optimization**: Use stroke-optimized icon paths from a reliable icon library
   - Source from Lucide, Heroicons, or similar stroke-based icon sets
   - Ensure paths are designed for 2px stroke width (matching CSS)
   - Verify icons are visually clear at 16px rendered size

5. **Maintain Compatibility**: Preserve all existing HTML structure and attributes
   - Keep same button classes and structure
   - Maintain aria-label and title attributes
   - Preserve event listeners and functionality

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm the root cause analysis of SVG fill/stroke conflicts.

**Test Plan**: Write tests that create feedback buttons and inspect the SVG attributes and computed styles. Run these tests on the UNFIXED code to observe the fill/stroke conflicts.

**Test Cases**:
1. **Fill Attribute Conflict Test**: Verify SVG has `fill="currentColor"` but computed style is `fill: none` (will fail on unfixed code)
2. **Visual Rendering Test**: Verify icons appear as unrecognizable shapes rather than thumbs (will fail on unfixed code)
3. **CSS Override Test**: Verify CSS `fill: none !important` overrides SVG fill attribute (will fail on unfixed code)
4. **Stroke Style Test**: Verify CSS applies `stroke: currentColor` but icons don't render properly (will fail on unfixed code)

**Expected Counterexamples**:
- SVG elements have fill attributes that conflict with CSS fill: none
- Icons render as unrecognizable shapes instead of clear thumbs up/down
- Possible causes: filled icon paths, fill attribute conflicts, stroke incompatibility

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL svgElement WHERE isBugCondition(svgElement) DO
  result := renderWithStrokeBasedIcon(svgElement)
  ASSERT expectedIconAppearance(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL interaction WHERE NOT isBugCondition(interaction) DO
  ASSERT originalFeedbackBehavior(interaction) = fixedFeedbackBehavior(interaction)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the interaction domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-visual interactions

**Test Plan**: Observe behavior on UNFIXED code first for button interactions, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Click Functionality Preservation**: Verify clicking buttons continues to register feedback and disable buttons
2. **Hover Effects Preservation**: Verify hover states continue to apply color changes and transforms
3. **Accessibility Preservation**: Verify aria-labels and titles continue to work with screen readers
4. **State Management Preservation**: Verify voted states continue to apply correct styling

### Unit Tests

- Test SVG icon rendering with stroke-based paths
- Test that no fill attributes exist on fixed SVG elements
- Test that icons are visually recognizable as thumbs up/down
- Test CSS compatibility with stroke: currentColor and fill: none

### Property-Based Tests

- Generate random button states and verify icons render correctly across all states
- Generate random CSS color values and verify icons inherit colors properly via currentColor
- Test that all non-icon functionality continues to work across many interaction scenarios

### Integration Tests

- Test complete feedback flow with new icons in browser environment
- Test visual appearance across different themes and color schemes
- Test that icon changes don't affect button layout or positioning
- Test accessibility with screen readers and keyboard navigation