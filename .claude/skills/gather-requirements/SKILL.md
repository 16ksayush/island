---
name: gather-requirements
description: Phase 1 Discovery — pairs the project-manager and solutions-architect to gather requirements, document them, and produce a plan. Use at the start of the project or whenever scope/requirements need to be (re)established before any code is written. Outputs docs/REQUIREMENTS.md, docs/ARCHITECTURE.md, docs/PLAN.md, and a Discovery Report with clarifying questions.
---

# Gather Requirements — PM × Architect Discovery

This skill runs the **Discovery & Blueprinting** loop by having the `project-manager` and `solutions-architect` subagents collaborate. It does NOT write feature code — it produces documentation and a plan, then stops for user sign-off.

## Roles in this pairing
- **project-manager** — owns scope, milestones, task breakdown, open questions, and the overall plan. Drives the loop and writes `docs/REQUIREMENTS.md` and `docs/PLAN.md`.
- **solutions-architect** — owns technical design: route signatures, payload schemas, the level→Drive-folder-ID config schema, and SSR-vs-static decision. Writes `docs/ARCHITECTURE.md`.

## Procedure
1. **PM — elicit & frame.** Dispatch `project-manager` to turn the user's goal into:
   - a functional requirements list (what the app must do),
   - non-functional requirements (theme, performance, hosting, security constraints),
   - a milestones checklist,
   - an explicit list of **open questions / unknowns** that block execution.
   Write these to `docs/REQUIREMENTS.md` and `docs/PLAN.md`. Then hand to ARCHITECT.
2. **ARCHITECT — technical design.** Dispatch `solutions-architect` to translate the requirements into:
   - FastAPI route signatures and request/response payloads (e.g. `/api/levels/{id}/photos`),
   - the level (0–18) → Google Drive Folder ID mapping schema,
   - SSR (Jinja2) vs static-HTML decision with rationale,
   - the frontend↔backend data-flow diagram.
   Write to `docs/ARCHITECTURE.md`. Flag any requirement that is ambiguous or technically risky back to the PM.
3. **PM — consolidate.** Dispatch `project-manager` to reconcile the architecture against requirements, finalize `docs/PLAN.md` (sequenced backlog), and assemble a **Discovery Report**.
4. **STOP.** Present the Discovery Report and the consolidated clarifying questions to the user. Do not proceed to implementation until the user answers / signs off.

## Hand-off narration
Use the project's hand-off syntax at each boundary:
```
>>> [AGENT_NAME] INITIALIZED >>>
...
<<< [AGENT_NAME] TERMINATED -> CALLING [NEXT_AGENT_NAME] <<<
```

## Output contract
On completion the repo must contain `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, and `docs/PLAN.md`, and the user must have a clear, numbered list of clarifying questions to answer.
