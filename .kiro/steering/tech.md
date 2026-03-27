# Technical Context

## Core Stack
This project is primarily built with:

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- Jinja2
- Playwright
- Google Gemini (`google-genai`)
- OpenAI
- Pinecone
- edge-tts
- moviepy
- Pillow
- ReportLab
- SQLite

## Technical Architecture
The system is not a generic web app.

It is a workflow capture, training generation, and automation platform with multiple connected stages:

1. workflow capture
2. roteiro generation
3. robot execution
4. media/document generation
5. Aura DAP reuse

Changes in one stage may affect downstream outputs.

When proposing technical changes, always consider compatibility across:
- capture
- generator
- executor
- video rendering
- SCORM generation
- PDF generation
- Aura DAP layer

## Backend Expectations
- FastAPI is the main application entrypoint.
- The backend handles dashboard routes, APIs, WebSocket updates, and background execution flows.
- Preserve async-friendly patterns where relevant.
- Do not introduce blocking-heavy behavior into sensitive execution paths without reason.
- Respect existing validation and shared contracts.

## Browser Automation Expectations
- Playwright is a core dependency, not a peripheral helper.
- The browser automation layer must be treated as fragile and high-impact.
- Senior X may involve dynamic rendering, asynchronous updates, iframes, and UI instability.
- Do not assume that a completed click or typing event means the application is ready.
- Prefer observable UI readiness over arbitrary fixed sleeps when possible.
- Be careful with selector brittleness, timing issues, focus problems, and state transitions.

## AI Expectations
- Gemini is the primary model for roteiro generation and vision-related tasks.
- OpenAI may exist as a secondary provider or fallback depending on the workflow.
- Pinecone supports retrieval and reuse for Aura DAP and related knowledge flows.
- AI output must be treated as probabilistic and should respect system contracts.
- Do not redesign pipelines around AI magic if deterministic validation is available.

## Media Pipeline Expectations
- edge-tts is the standard narration layer.
- moviepy is the main video composition/rendering layer.
- Pillow and ReportLab support image and PDF generation.
- Changes to narration timing, rendering, or media assets may affect the final training experience.
- Preserve compatibility between roteiro structure and final generated assets.

## Storage Expectations
- SQLite is used for local operational memory and cache.
- JSON artifacts are part of the production workflow, not temporary scratch data.
- Treat roteiro files as durable system artifacts.
- Avoid unsafe writes or partial writes to files consumed by other stages.

## Environment and Secrets
- Secrets must come from `.env`.
- Never hardcode credentials, tokens, API keys, or sensitive endpoints.
- Environment-based configuration is part of the project contract.
- If a feature depends on a new environment variable, document it clearly.

## Dependency and Command Guidance
- Prefer minimal dependency changes.
- Do not introduce a new library unless there is a clear technical reason.
- Prefer consistency with the existing project stack.
- When suggesting commands, prefer the project’s real operational flow.

Common project commands include:
- install dependencies
- install Playwright Chromium
- run the main app
- rebuild the action library
- generate SCORM
- generate PDF
- execute the robot in record or render mode

## What Kiro Should Optimize For
Optimize technical suggestions for:
- reliability,
- low regression risk,
- compatibility with the existing pipeline,
- observability,
- maintainability,
- and safe automation behavior.

## What Kiro Should Avoid
Avoid:
- unnecessary framework swaps,
- broad refactors without request,
- fragile selector assumptions,
- hidden side effects,
- unsafe file writes,
- direct secret embedding,
- and generic advice that ignores Playwright, Senior X, or the multi-output pipeline.