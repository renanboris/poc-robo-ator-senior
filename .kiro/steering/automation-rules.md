# Automation Rules

## Purpose
These rules define how Kiro should reason about, modify, and validate this codebase.

## General Behavior
- Prefer the smallest safe patch that solves the problem.
- Preserve the current architecture unless a larger refactor is explicitly requested.
- Explain the root cause before proposing broad changes.
- When multiple solutions exist, prefer the one with lower regression risk.
- Do not rewrite unrelated modules just because a cleaner design is possible.
- Keep compatibility with the current Training OS pipeline unless the change explicitly targets a breaking redesign.

## Safety First
- Treat automation in Senior X as high risk.
- Assume some actions may be destructive even if the code path looks harmless.
- Be cautious around flows involving save, delete, confirmation, processing, submission, closing periods, or irreversible ERP actions.
- If a flow may cause side effects, prefer a dry-run, visual validation, or an explicit guardrail in code.

## Project Architecture Rules
- Never bypass the single background-task protection enforced in `app.py`.
- Never mutate server state directly if `_set_estado()` is the intended path.
- Always use `limpar_nome()` from `utils.py` for filename sanitization.
- Always validate user-controlled paths through the project’s safe path validation flow.
- Use atomic writes for JSON artifacts that other processes depend on.
- Preserve the required roteiro structure: `metadata`, `configuracao_gravacao`, and `passos`.
- Preserve the final completion step contract when generating or editing roteiros.
- Never hardcode credentials, tokens, or secrets.

## Editing Strategy
- Before editing, identify the impacted modules and keep the scope explicit.
- Prefer patching the nearest responsible module instead of spreading logic across many files.
- Avoid duplicate helper functions when a canonical utility already exists.
- Avoid local hacks that bypass shared contracts or validators.
- When touching capture, generator, executor, or DAP logic, consider downstream effects on video, SCORM, PDF, and extension behavior.

## Automation and Playwright Guidance
- Prefer resilient strategies over brittle selectors.
- Consider timing issues from dynamic UI updates, SPA rendering, iframes, and asynchronous state transitions.
- Do not assume machine speed equals application readiness.
- Prefer observable readiness checks over blind sleeps when possible.
- When proposing waits, explain what state is being awaited.

## AI and Generation Guidance
- Preserve the pedagogical role of the roteiro as the central artifact.
- Keep generated outputs aligned with the same source of truth whenever possible.
- Do not introduce changes that break compatibility between capture, generation, rendering, and DAP reuse.
- Favor reusable action mapping over one-off hardcoded behavior.

## Validation Expectations
- After proposing a change, always suggest a minimal manual test plan.
- For risky changes, include:
  - preconditions,
  - execution steps,
  - expected result,
  - regression risks.
- If confidence is low, say so clearly instead of pretending certainty.

## Response Style
- Be practical and direct.
- Prefer concrete implementation guidance over abstract theory.
- When useful, separate:
  1. diagnosis,
  2. patch plan,
  3. code change,
  4. test steps.