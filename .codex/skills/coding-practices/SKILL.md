---
name: coding-practices
description: Use when implementing, refactoring, or reviewing code in this project, especially when changing prompts, schemas, config-driven behavior, or cleanup scope.
---

# Coding Practices

## Core Rules

- Put prompts, templates, and reusable user-facing text in config files. Do not hard-code them in service or UI code.
- If a label, field, or schema changes, rename it consistently across backend, frontend, storage, scripts, prompts, and tests in the same change.
- Remove dead paths, obsolete fields, dormant UI branches, and legacy helpers. Only live production code should remain unless a real migration requires otherwise.
- Do not replace a failing high-quality path with a lower-quality heuristic fallback. Retry, repair, or return a clear failure.
- Keep one source of truth. New countries, use cases, and prompt vocabulary should come from config rather than hard-coded conditionals.
- When output contracts change, update tests first and verify backend and frontend together.

## Working Pattern

1. Search the repo for every reference before editing.
2. Update the source-of-truth config or schema first.
3. Update all call sites and storage contracts in the same pass.
4. Add a migration only when live data must be preserved.
5. Run a final search to confirm the old label or legacy path is gone.

## Avoid

- Hard-coded prompt text in Python or TypeScript.
- Partial renames that leave legacy names behind.
- Parallel legacy formats without an explicit migration need.
- Demo or fallback content that diverges from live behavior.
- “Temporary” compatibility code with no removal plan.
