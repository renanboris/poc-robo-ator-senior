# Project Structure

## Purpose
This file explains how the codebase is organized and how Kiro should navigate it safely.

Use it to understand:
- where each responsibility lives,
- which modules are core to the pipeline,
- which artifacts are system-critical,
- and how to avoid unsafe edits.

## Mental Model
This project is a multi-stage pipeline.

The system should be understood in this order:
1. capture user workflow
2. transform capture into roteiro
3. execute or replay roteiro
4. generate delivery artifacts
5. reuse knowledge in Aura DAP

When editing this codebase, prefer understanding the pipeline first instead of treating files as isolated utilities.

## Core Pipeline Modules
These are the main files that define the system’s backbone:

- `capture.py`  
  Records user interaction in Senior X through Playwright and produces raw capture data.

- `generator_engine.py`  
  Converts raw capture into a structured roteiro JSON using AI and retrieval support.

- `main.py`  
  Replays the roteiro to execute the workflow and drive recording or rendering flows.

- `scorm_builder.py`  
  Generates SCORM packages from a roteiro.

- `pdf_builder.py`  
  Generates PDF playbooks from a roteiro.

- `lego_builder.py`  
  Rebuilds `biblioteca_acoes.json` from saved roteiros to improve action reuse.

- `dap_engine.py`  
  Powers Aura DAP retrieval and question-answering behavior.

## Platform and Runtime Modules
These modules support orchestration, delivery, and runtime behavior:

- `app.py`  
  Main FastAPI entrypoint, dashboard backend, API surface, WebSocket updates, and background task orchestration.

- `vision_engine.py`  
  Self-healing locator logic and fallback strategies when UI elements change.

- `cursor_engine.py`  
  Humanized cursor movement for visual realism during automation and recording.

- `validator.py` and `validator_hitl.py`  
  Quality validation for generated roteiros.

- `utils.py`  
  Shared utilities. Treat `limpar_nome()` as the canonical filename sanitizer.

- `reprocessar.py`  
  CLI utility for reprocessing existing roteiros.

## Main Directories
These directories hold the operational artifacts of the product:

- `roteiros_salvos/`  
  Central JSON artifacts of the system. Treat these as durable production assets.

- `audios_gerados/`  
  Generated narration audio files.

- `videos_gerados/`  
  Intermediate rendering outputs.

- `videos_prontos/`  
  Final MP4 outputs.

- `scorm_exports/`  
  SCORM ZIP packages.

- `documentacao_pdf/`  
  Generated PDF playbooks.

- `missoes_ativas/`  
  Mission JSON artifacts for gamified flows.

- `templates/`  
  Jinja2 templates for the web UI.

- `extension/`  
  Aura DAP browser extension code.

- `contracts/`  
  Shared contracts or schemas.

- `repositories/`  
  Data access layer modules.

- `relatorios_execucao/`  
  Robot execution reports.

- `diagnostico_falhas/`  
  Failure diagnostics and debugging outputs.

- `old_but_gold/`  
  Archived code kept for historical reference. Do not treat it as the default source of truth unless explicitly needed.

## System-Critical Data Files
These files are important to the pipeline and should be edited with care:

- `biblioteca_acoes.json`  
  Reusable action memory generated from saved roteiros.

- `brain.db`  
  Selector memory used by self-healing flows.

- `aura_cache.db`  
  Aura DAP cache store.

- `generator_prompt.txt`  
  Prompt contract for roteiro generation.

- `aura_prompt.txt`  
  Prompt contract for Aura behavior.

## Navigation Rules for Kiro
When asked to change something, navigate by responsibility:

- If the issue is about recording or user action capture, start with `capture.py`.
- If the issue is about roteiro generation quality or structure, start with `generator_engine.py`.
- If the issue is about playback, execution, or rendering behavior, start with `main.py`.
- If the issue is about SCORM output, start with `scorm_builder.py`.
- If the issue is about PDF documentation, start with `pdf_builder.py`.
- If the issue is about reusable action memory, inspect `lego_builder.py` and `biblioteca_acoes.json`.
- If the issue is about DAP, retrieval, or Aura answers, inspect `dap_engine.py`, `aura_cache.db`, and extension-related code.
- If the issue is about dashboard state, routes, or background execution, inspect `app.py`.

## Architecture Rules
These conventions are mandatory:

- `app.py` enforces a single background task at a time. Never bypass that protection.
- All server state transitions must go through `_set_estado()`.
- Never mutate shared server state directly when `_set_estado()` is the intended contract.
- Always use `limpar_nome()` from `utils.py` for filename sanitization.
- All user-controlled path operations must go through the project’s safe path validation flow.
- Use atomic writes for JSON artifacts consumed by other parts of the system.
- Every roteiro must preserve its required structure.
- The completion step contract must be preserved.
- Secrets must stay in `.env`, never inside code.

## Editing Strategy
When modifying this project:

- Prefer the nearest responsible file instead of scattering logic across multiple modules.
- Preserve contracts between capture, roteiro, execution, and output generators.
- Avoid duplicate utility functions when a canonical helper already exists.
- Avoid broad refactors unless explicitly requested.
- Consider downstream effects before changing shared artifacts or schemas.

## What Matters Most
The most important structural idea in this codebase is this:

The roteiro is the central contract, and most major modules either create it, consume it, transform it, or derive artifacts from it.

Any structural change that weakens that contract should be treated as high risk.