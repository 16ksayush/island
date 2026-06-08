# Plan & Backlog — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **DRAFT** — backlog ready; Phase 2 starts after asset data (Open Q1) is settled.

## Milestones
- [x] **M0 — Discovery:** dual-theme PRD captured; requirements, architecture, plan documented; design questions answered.
- [ ] **M1 — Scaffold & secure:** PRD file tree (`app/`, `static/`, `templates/`), `requirements.txt`, `.env.example` (`GD_API_KEY`, `GD_ROOT_FOLDER`), hardened `.gitignore`, audio tree `static/audio/{global,horror,sea}/` (+ `_fallback/`).
- [ ] **M2 — Backend dynamic core:** `drive_service.py` (Drive client under `GD_ROOT_FOLDER`, child discovery for dynamic scaling, `missing/` image fallback), `main.py` routes incl. theme cookie.
- [ ] **M3 — Theme system:** `style.css` `.theme-horror`/`.theme-sea`, global toggle on every page, cookie + sessionStorage persistence, SSR theme read.
- [ ] **M4 — Landing grid:** dynamic Corridor Grid ⇄ Island Map; renders configured levels + missing tiles.
- [ ] **M5 — Level pages:** `/level/{id}` (`level.html`) room/beach presentation; image rendering via proxy.
- [ ] **M6 — Audio engine:** global ambient per theme + per-level crossfade, auto-play-safe.
- [ ] **M7 — Harden & test:** error handling, missing-folder paths, security audit per file, local `uvicorn` smoke test.
- [ ] **M8 — Deploy:** Render/Railway config, `GD_API_KEY` env var, live verification.

## Sequenced backlog (Phase 2 — `orchestrate-build` after sign-off)
| # | Task | Owner | Depends on |
|---|---|---|---|
| T1 | Scaffold PRD dir tree + `requirements.txt` (fastapi, uvicorn, jinja2, httpx) | project-manager | M0 |
| T2 | Hardened `.gitignore` + `.env.example` (`GD_API_KEY`, `GD_ROOT_FOLDER`) | security-engineer | T1 |
| T3 | `GD_ROOT_FOLDER` parent link config (real or placeholder) + audio tree layout | solutions-architect | Q1 |
| T4 | `drive_service.py`: Drive client under parent folder, child-discovery scaling, `missing/` image fallback | backend-engineer | T3 |
| T5 | `main.py`: `/`, `/level/{id}`, `/api/levels`, `/api/levels/{id}/photos`, `/api/.../media/...`, theme cookie | backend-engineer | T4 |
| T6 | Security audit of backend files (key isolation, missing-path safety) | security-engineer | T5 |
| T7 | `style.css` dual-theme classes + global theme toggle (cookie + sessionStorage) | frontend-engineer | T5 |
| T8 | `index.html` dynamic Corridor/Island grid | frontend-engineer | T7 |
| T9 | `level.html` room/beach level page + proxied images | frontend-engineer | T7, T5 |
| T10 | Audio crossfade engine (global ⇄ level), auto-play-safe | frontend-engineer | T8, T9, Q1 |
| T11 | Security audit of frontend files | security-engineer | T10 |
| T12 | Local `uvicorn` smoke test + missing-folder + theme-toggle verification | project-manager | T6, T11 |
| T13 | Render/Railway deploy config + instructions | project-manager | T12 |

## Gate
✅ **Discovery complete.** All design questions resolved; building with placeholders (`GD_ROOT_FOLDER` + audio stubs filled in locally later). Drive shared public (`GD_API_KEY`); `missing/` folder holds stock images + audio. Phase 2 (`orchestrate-build`) is unblocked — awaiting the user's go to start writing code.
