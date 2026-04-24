# Legacy → Next Integration

## Overview

Two systems collaborate to produce and consume operational knowledge:

| System | Role | Key artifact |
|--------|------|-------------|
| **Legacy** (`poc-robo-ator-senior`) | Operational factory — captures workflows, generates roteiros, executes robots | Shadow JSONL (`shadow_exports/*.jsonl`) |
| **Next** (`senior-training-os-next` / CIL) | Semantic brain — classifies knowledge, promotes skills, enriches the planner | `KnownSkill` in `SkillMemory` |

The bridge between them is the **Next Integration Diamond** pipeline implemented in `next_integration.py`.

---

## Data Flow

```
capture_dual_output.py
        │
        ▼  (shadow JSONL)
shadow_exports/*.jsonl
        │
        ▼
Triage_Pipeline.ingest_shadow_file()
  ├── accepted  ──► LegacyBridge.map_to_observed_action()
  │                       │
  │                       ▼
  │               ScreenObserver.classify_screen()
  │               ScreenObserver.infer_component_family()
  │                       │
  │                       ▼
  │               Promotion_Gate_Engine.evaluate_promotion_readiness()
  │                       │
  │                       ▼
  │               LegacyBridge.deliver_comparative_context()
  │                       │
  │                       ▼
  │               ShadowModeRunner.receive_context()  (optional)
  │
  ├── review    ──► stored for human triage
  └── rejected  ──► logged and discarded
```

---

## Field Mapping: Shadow Event → ObservedAction

| Shadow JSONL field | ObservedAction field | Layer |
|--------------------|---------------------|-------|
| `id_acao` | `action_id`, `provenance.original_event_id` | A |
| `captured_at` | `provenance.captured_at` | A |
| `acao` | `action_type` | A |
| `capture_scope` | *(stored in artifacts)* | A |
| `elemento_alvo.seletor_hint` | `raw_target.selector` | A |
| `elemento_alvo.iframe_hint` | `raw_target.iframe_hint` | A |
| `elemento_alvo.html_hint` | `raw_target.html_hint`, `artifacts["html_hint"]` | A |
| `elemento_alvo.coordenadas_relativas` | `raw_target.coords`, `artifacts["coords"]` | A |
| `elemento_alvo.screenshot_referencia` | `screen_before` | A |
| `valor_input` | `raw_target.valor_input` | A |
| `page_title` | *(used by ScreenObserver)* | A |
| `url_hint` | *(used by ScreenObserver)* | A |
| `semantic_action` | `semantic_action` | B |
| `business_entity` | `business_entity` | B |
| `business_target` | `business_target` | B |
| `pattern_detectado` | `pattern` | B |
| `intencao_semantica` | `intencao_semantica` | B |
| `screen_family` | `screen_family` | B |
| `component_family` | `component_family` | B |
| `expected_effect` / `validacao_esperada.alvo` | `expected_effect` | B |
| `elemento_alvo.confianca_captura` | `confidence` (alta→0.9, media→0.6, baixa→0.3) | C |
| `is_noise` | `is_noise`, `confidence=0.1` if True | C |
| `observed_effect` | `observed_effect` | C |

---

## Component Responsibilities

| Module | Responsibility |
|--------|---------------|
| `shadow_builder.py` | Produces shadow JSONL with `expected_effect` top-level field |
| `shadow_schema.py` | Validates events against the 3-layer canonical schema |
| `triage_pipeline.py` | Classifies events as accepted / review / rejected |
| `legacy_bridge.py` | Reads JSONL, maps to ObservedAction, delivers comparative context |
| `observed_action_adapter.py` | Field-level mapping from shadow dict to ObservedAction |
| `screen_observer.py` | Classifies screen_family and component_family |
| `promotion_engine.py` | Evaluates promotion gates (Level 0–3) |
| `promotion_models.py` | PromotionBenchmark thresholds |
| `skill_models.py` | KnownSkill dataclass with full provenance |
| `skill_memory.py` | Storage and retrieval of KnownSkill records |
| `next_integration.py` | End-to-end wiring facade |
| `CIL/core/planner_cil.py` | Planner enriched with promoted skill hints |
