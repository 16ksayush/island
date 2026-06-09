---
name: design-webpage
description: Design phase — turns the gathered requirements (docs/REQUIREMENTS.md, docs/ARCHITECTURE.md) into a reviewable visual + interaction design via the ui-designer subagent: a design system, CSS tokens, and clickable static mockups for both themes. Use after requirements are gathered and before frontend implementation, or standalone to (re)design the UI. Runs inside orchestrate-build between architecture and frontend build.
---

# Design Webpage — Requirements → Visual Design

This skill produces the design that the `frontend-engineer` later implements. It is the bridge between **what** (requirements/architecture) and **how it looks/feels**. It does not touch the backend.

## Procedure
1. **Preconditions.** Confirm `docs/REQUIREMENTS.md` and `docs/ARCHITECTURE.md` exist and reflect the latest decisions (themes, dynamic levels, `/level/{id}`, `.theme-*` classes, crossfade). If missing, run `gather-requirements` first.
2. **Design.** Dispatch the `ui-designer` subagent to produce, in `design/`:
   - `DESIGN_SYSTEM.md` (tokens, type, components, motion, a11y),
   - `tokens.css` (`.theme-horror` / `.theme-sea` custom properties),
   - static mockups: `mockups/landing-{horror,sea}.html`, `mockups/level-{horror,sea}.html`, with a working theme toggle and placeholder media.
3. **Review.** Open the mockups (`open design/mockups/landing-horror.html` on macOS) and present them to the user for look/feel sign-off. Capture requested changes and iterate via `ui-designer`.
4. **Handoff.** On approval, the design tokens/specs flow to the `frontend-engineer`, who adopts `tokens.css` into `static/style.css` and builds the SSR templates 1:1 with the mockups.

## Hand-off narration
```
>>> UI_UX_DESIGNER INITIALIZED >>>
...
<<< UI_UX_DESIGNER TERMINATED -> CALLING FRONTEND_ENGINEER <<<
```

## Output contract
On completion the repo contains `design/DESIGN_SYSTEM.md`, `design/tokens.css`, and four static mockups, and the user has approved (or requested changes to) the look of both themes.

## Notes
- Mockups are static and backend-free — for approval only; production rendering is SSR via Jinja2.
- Keep `design/` in sync with `docs/` per the Documentation Policy.
