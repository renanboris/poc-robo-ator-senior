# Dual Shadow Schema

The canonical shadow schema organises every captured interaction event into
three semantic layers.  Each layer has a distinct purpose and a different
downstream consumer.

---

## Layer A — Raw Observation

*What happened, where, and how it was seen.*

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id_acao` | int | ✅ | Sequential event identifier |
| `captured_at` | ISO 8601 string | ✅ | UTC timestamp of capture |
| `acao` | string | ✅ | Raw action type (`clique`, `digitacao`, …) |
| `capture_scope` | `"shell"` \| `"module_iframe"` | ✅ | Where the action occurred |
| `seletor_hint` | string | ✅ | Primary CSS / aria selector |
| `iframe_hint` | string \| null | — | Iframe context if applicable |
| `html_hint` | string | ✅ | Outer HTML snippet (≤300 chars) |
| `coordenadas_relativas` | `{x_pct, y_pct, w_pct, h_pct}` | ✅ | Relative bounding box |
| `screenshot_referencia` | base64 string \| null | — | Screenshot at capture time |
| `valor_input` | string | ✅ | Value typed/selected (empty string if none) |
| `page_title` | string | ✅ | Browser page title |
| `url_hint` | string | ✅ | Current URL |

---

## Layer B — Interpretation

*What the action means, what goal it represents, what entity is involved.*

| Field | Type | Vocabulary | Description |
|-------|------|-----------|-------------|
| `semantic_action` | string | `fill`, `search`, `confirm`, `delete`, `save`, `open`, `navigate`, `select`, `close` | Semantic intent |
| `business_entity` | string | `pasta`, `documento`, `campo`, `menu`, `selecao`, `elemento`, `cliente`, `pedido` | Domain entity |
| `business_target` | string | — | Label / description of the target element |
| `pattern_detectado` | string | `menu_navigation`, `form_fill`, `button_click`, `table_selection`, `breadcrumb_navigation`, `toolbar_action`, `modal_action`, `tree_item_open`, `search_debounce`, `unknown` | UI interaction pattern |
| `intencao_semantica` | string | — | Human-readable intent (≤60 chars) |
| `screen_family` | string | `ged_list`, `ged_form`, `ged_tree`, `sign_inbox`, `sign_envelope`, `erp_form`, `erp_list`, `modal_confirm`, `modal_form`, `shell_navigation`, `unknown` | Screen classification |
| `component_family` | string | `toolbar_button`, `context_menu_item`, `tree_node`, `form_input`, `checkbox_row`, `table_row`, `modal_button`, `unknown` | Component classification |
| `expected_effect` | string | — | What should change after the action |

---

## Layer C — Quality Evidence

*How reliable the capture was, what signals are missing, whether the record is ready for promotion.*

| Field | Type | Description |
|-------|------|-------------|
| `confianca_captura` | `"alta"` \| `"media"` \| `"baixa"` | Capture confidence |
| `is_noise` | bool | True if the event is likely noise |
| `missing_signals` | list[string] | Layer B fields that are empty or `"unknown"` |
| `observed_effect` | string \| null | What actually changed (inferred from screenshot delta) |
| `promotion_readiness` | bool | True if ready for Level 1 promotion |
| `review_required` | bool | True if human review is needed |

---

## Complete Example Event

```json
{
  "id_acao": 42,
  "captured_at": "2024-01-15T10:30:00Z",
  "acao": "clique",
  "capture_scope": "shell",
  "seletor_hint": "[aria-label='GED']",
  "iframe_hint": null,
  "html_hint": "<a class='menu-item' aria-label='GED'>GED</a>",
  "coordenadas_relativas": {"x_pct": 0.05, "y_pct": 0.35, "w_pct": 0.08, "h_pct": 0.04},
  "screenshot_referencia": null,
  "valor_input": "",
  "page_title": "Senior X",
  "url_hint": "https://platform.senior.com.br/",

  "semantic_action": "open",
  "business_entity": "menu",
  "business_target": "GED",
  "pattern_detectado": "menu_navigation",
  "intencao_semantica": "Abrir módulo GED pelo menu lateral",
  "screen_family": "shell_navigation",
  "component_family": "toolbar_button",
  "expected_effect": "Conteúdo ou modal aberto",

  "confianca_captura": "alta",
  "is_noise": false,
  "missing_signals": [],
  "observed_effect": null,
  "promotion_readiness": true,
  "review_required": false
}
```
