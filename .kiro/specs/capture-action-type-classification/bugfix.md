# Bugfix Requirements Document

## Introduction

Two related bugs cause incorrect action type classification across the capture and runtime layers of the pipeline.

In the capture layer (`capture.py`), the `blur` event handler assigns `preencher_campo` to all input elements without inspecting the `type` attribute. This means checkboxes, radio buttons, and toggle inputs are recorded with the wrong action type, producing roteiros that are structurally incorrect from birth.

In the runtime layer (`vision_engine.py`), the executor does not inspect the real DOM type of an element before running `preencher_campo` logic. When a step targets a checkbox or radio — whether from a bad capture or a legacy roteiro — the runtime blindly executes `Ctrl+A` + `Backspace` + `fill()` on a non-text element, causing visual glitches (screen flashing blue) and incorrect automation behavior.

Both bugs share the same root condition: the element's `input[type]` is not consulted before deciding how to interact with it.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a `blur` event fires on an `<input type="checkbox">` or `<input type="radio">` element with a value THEN the system records the interaction with `"acao": "preencher_campo"` instead of `"acao": "clique"`

1.2 WHEN a `blur` event fires on an `<input type="submit">`, `<input type="button">`, or `<input type="image">` element THEN the system records the interaction with `"acao": "preencher_campo"` instead of `"acao": "clique"`

1.3 WHEN the runtime executes a roteiro step with `"acao": "preencher_campo"` and the real DOM element is a checkbox or radio THEN the system executes `Ctrl+A` + `Backspace` + `fill()` on the element, causing visual glitches and incorrect behavior

### Expected Behavior (Correct)

2.1 WHEN a `blur` event fires on an `<input type="checkbox">` or `<input type="radio">` element THEN the system SHALL record the interaction with `"acao": "clique"` and set `valor` to `"marcado"` or `"desmarcado"` based on the element's checked state

2.2 WHEN a `blur` event fires on an `<input type="submit">`, `<input type="button">`, or `<input type="image">` element THEN the system SHALL record the interaction with `"acao": "clique"`

2.3 WHEN the runtime is about to execute `preencher_campo` and the real DOM element type is `checkbox` or `radio` THEN the system SHALL convert the action to a `clique` interaction, log a warning, and skip the fill logic entirely

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a `blur` event fires on an `<input type="text">`, `<input type="email">`, `<input type="password">`, `<input type="number">`, `<input type="search">`, or any other non-checkable, non-button input type with a value THEN the system SHALL CONTINUE TO record the interaction with `"acao": "preencher_campo"` and the field value

3.2 WHEN a `blur` event fires on a `<textarea>` or a `contentEditable` element with a value THEN the system SHALL CONTINUE TO record the interaction with `"acao": "preencher_campo"` and the field value

3.3 WHEN a `blur` event fires on a `<select>` element THEN the system SHALL CONTINUE TO record the interaction with `"acao": "preencher_campo"` and the selected value

3.4 WHEN the runtime executes `preencher_campo` on a standard text input, textarea, or select element THEN the system SHALL CONTINUE TO execute the existing `Ctrl+A` + `Backspace` + `fill()` logic unchanged

3.5 WHEN the runtime executes any action other than `preencher_campo` THEN the system SHALL CONTINUE TO behave exactly as before, with no change to click, double-click, right-click, or digitar_e_enter flows

---

## Bug Condition Pseudocode

**Bug Condition — Capture Layer:**

```pascal
FUNCTION isBugCondition_Capture(element)
  INPUT: element of type HTMLInputElement
  OUTPUT: boolean

  RETURN element.tagName = "INPUT"
    AND element.type IN ("checkbox", "radio", "submit", "button", "image")
    AND capturedAction = "preencher_campo"
END FUNCTION
```

```pascal
// Property: Fix Checking — Capture Layer
FOR ALL element WHERE isBugCondition_Capture(element) DO
  result ← captureInteraction'(element)
  ASSERT result.acao = "clique"
END FOR

// Property: Preservation Checking — Capture Layer
FOR ALL element WHERE NOT isBugCondition_Capture(element) DO
  ASSERT captureInteraction(element) = captureInteraction'(element)
END FOR
```

**Bug Condition — Runtime Layer:**

```pascal
FUNCTION isBugCondition_Runtime(step, domElement)
  INPUT: step of type RoteiroStep, domElement of type DOMElement
  OUTPUT: boolean

  RETURN step.acao = "preencher_campo"
    AND domElement.type IN ("checkbox", "radio")
END FUNCTION
```

```pascal
// Property: Fix Checking — Runtime Layer
FOR ALL (step, domElement) WHERE isBugCondition_Runtime(step, domElement) DO
  result ← executeStep'(step, domElement)
  ASSERT no_ctrl_a_backspace_fill(result)
    AND element_was_clicked(result)
    AND warning_was_logged(result)
END FOR

// Property: Preservation Checking — Runtime Layer
FOR ALL (step, domElement) WHERE NOT isBugCondition_Runtime(step, domElement) DO
  ASSERT executeStep(step, domElement) = executeStep'(step, domElement)
END FOR
```
