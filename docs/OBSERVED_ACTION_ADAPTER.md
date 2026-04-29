# ObservedAction Adapter

`ObservedAction_Adapter` (in `observed_action_adapter.py`) converts a Legacy
shadow event dict into a fully-populated `ObservedAction` contract.

---

## Field Mapping Table

| Shadow JSONL field | ObservedAction field | Notes |
|--------------------|---------------------|-------|
| `id_acao` | `action_id`, `provenance.original_event_id` | |
| `acao` | `action_type` | |
| `elemento_alvo.seletor_hint` | `raw_target.selector` | |
| `elemento_alvo.iframe_hint` | `raw_target.iframe_hint` | |
| `elemento_alvo.html_hint` | `raw_target.html_hint`, `artifacts["html_hint"]` | |
| `elemento_alvo.coordenadas_relativas` | `raw_target.coords`, `artifacts["coords"]` | |
| `elemento_alvo.screenshot_referencia` | `screen_before` | base64 reference |
| `valor_input` | `raw_target.valor_input` | |
| `elemento_alvo.confianca_captura` | `confidence` | alta→0.9, media→0.6, baixa→0.3 |
| `is_noise` | `is_noise` | if True → confidence=0.1, review_required=True |
| `semantic_action` | `semantic_action` | |
| `business_entity` | `business_entity` | |
| `business_target` | `business_target` | |
| `pattern_detectado` | `pattern` | |
| `intencao_semantica` | `intencao_semantica` | |
| `screen_family` | `screen_family` | enriched by ScreenObserver if missing |
| `component_family` | `component_family` | enriched by ScreenObserver if missing |
| `expected_effect` / `validacao_esperada.alvo` | `expected_effect` | top-level field takes priority |
| `observed_effect` | `observed_effect` | inferred from screenshot if not explicit |
| `id_acao` + source_file + `captured_at` | `provenance` | full traceability |

---

## Confidence Mapping

| `confianca_captura` | `confidence` |
|---------------------|-------------|
| `"alta"` | `0.9` |
| `"media"` | `0.6` |
| `"baixa"` | `0.3` |
| `is_noise=True` | `0.1` (overrides all) |

---

## Edge Cases

**`is_noise=True`**
Confidence is forced to `0.1` and `review_required` is set to `True`
regardless of `confianca_captura`.

**Missing `expected_effect`**
The adapter falls back to `validacao_esperada.alvo`.  If both are empty,
`expected_effect` is an empty string and `review_required` is set to `True`.

**`observed_effect` inference**
1. If the shadow event has an explicit `observed_effect` field, it is used.
2. If `screenshot_referencia` is present, a sentinel
   `"__pending_visual_inference__:<expected_effect>"` is stored.
   Downstream vision engines replace this with the actual inferred effect.
3. If neither is available, `observed_effect` is `null` and
   `review_required` is set to `True`.

---

## Example

**Input (shadow event):**
```json
{
  "id_acao": 42,
  "captured_at": "2024-01-15T10:30:00Z",
  "acao": "clique",
  "is_noise": false,
  "valor_input": "",
  "semantic_action": "open",
  "business_entity": "menu",
  "business_target": "GED",
  "pattern_detectado": "menu_navigation",
  "screen_family": "shell_navigation",
  "component_family": "toolbar_button",
  "expected_effect": "Conteúdo ou modal aberto",
  "elemento_alvo": {
    "seletor_hint": "[aria-label='GED']",
    "iframe_hint": null,
    "html_hint": "<a>GED</a>",
    "coordenadas_relativas": {"x_pct": 0.05, "y_pct": 0.35, "w_pct": 0.08, "h_pct": 0.04},
    "screenshot_referencia": null,
    "confianca_captura": "alta"
  }
}
```

**Output (ObservedAction):**
```python
ObservedAction(
    action_id=42,
    action_type="clique",
    raw_target=RawTarget(selector="[aria-label='GED']", iframe_hint=None, ...),
    screen_before=None,
    confidence=0.9,
    is_noise=False,
    review_required=True,   # observed_effect could not be inferred
    screen_family="shell_navigation",
    component_family="toolbar_button",
    pattern="menu_navigation",
    expected_effect="Conteúdo ou modal aberto",
    observed_effect=None,
    provenance=Provenance(original_event_id=42, source_file="...", captured_at="2024-01-15T10:30:00Z")
)
```
