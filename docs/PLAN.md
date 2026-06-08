# Plan & Backlog — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Discovery COMPLETE — backlog sequenced and ready.** Asset reality confirmed; architecture validated (payload schemas §4.1, in-memory level→folder map §5.1, missing-audio data flow corrected). Six technical risks triaged: R1 (open-proxy) and R6 (MIME echo) folded in as hard acceptance criteria; R4 (pagination) and R5 (empty-but-present folder) locked by default; R2 (discovery freshness) and R3 (fallback determinism) carry recommended defaults but remain user-confirmable. Phase 2 (`orchestrate-build`) is unblocked, building with placeholders. Awaiting the user's go.

## Milestones
- [x] **M0 — Discovery:** dual-theme PRD captured; requirements, architecture, plan documented; design questions answered.
- [ ] **M1 — Scaffold & secure:** PRD file tree (`app/`, `static/`, `templates/`), `requirements.txt`, `.env.example` (`GD_API_KEY`, `GD_ROOT_FOLDER`), hardened `.gitignore`, audio tree `static/audio/{global,horror,sea}/` (missing-level fallback audio is from Drive `missing/`, not local — D6/D9).
- [ ] **M2 — Backend dynamic core:** `drive_service.py` (Drive client under `GD_ROOT_FOLDER`, child discovery for dynamic scaling, `missing/` image fallback), `main.py` routes incl. theme cookie.
- [ ] **M3 — Theme system:** `style.css` `.theme-horror`/`.theme-sea`, global toggle on every page, cookie + sessionStorage persistence, SSR theme read.
- [ ] **M4 — Landing grid:** dynamic Corridor Grid ⇄ Island Map; renders configured levels + missing tiles.
- [ ] **M5 — Level pages:** `/level/{id}` (`level.html`) room/beach presentation; image rendering via proxy.
- [ ] **M6 — Audio engine:** global ambient per theme + per-level crossfade, auto-play-safe.
- [ ] **M7 — Harden, test & verify:** error handling, missing-folder paths, security audit per file, **QA_TESTER pytest suite (Drive mocked) + behavioral checks**, local `uvicorn` smoke test. No unit frozen until audited AND tests pass.
- [ ] **M8 — Deploy:** Render/Railway config, `GD_API_KEY` env var, live verification.

## Sequenced backlog (Phase 2 — `orchestrate-build` after sign-off)
| # | Task | Owner | Depends on |
|---|---|---|---|
| T1 | Scaffold PRD dir tree + `requirements.txt` (fastapi, uvicorn, jinja2, httpx) | project-manager | M0 |
| T2 | Hardened `.gitignore` + `.env.example` (`GD_API_KEY`, `GD_ROOT_FOLDER`) | security-engineer | T1 |
| T3 | `GD_ROOT_FOLDER` parent link config (placeholder in `.env.example`) + audio tree layout | solutions-architect | T1 |
| T4 | `drive_service.py`: Drive client under parent folder, child-discovery scaling, `missing/` image+audio fallback. **AC: missing-level fallback re-rolls a fresh random image+audio from `missing/` on every `/photos` call (R3); builds `folder_index`/`missing_folder_id`/`levels` once and caches, refreshed only via `POST /api/refresh` (R2).** | backend-engineer | T3 |
| T5 | `main.py`: `/`, `/level/{id}`, `/api/levels`, `/api/levels/{id}/photos`, `/api/.../media/...`, theme cookie. **AC: media proxy echoes upstream Drive `Content-Type` (image/* vs audio/mpeg), never hardcoded (R6); empty-but-present numbered folder falls through to missing fallback (R5, default); discovery is startup-built + cached with an optional manual `POST /api/refresh` (R2, default); Drive `files.list` handles `pageToken` defensively (R4).** | backend-engineer | T4 |
| T6 | Security audit of backend files (key isolation, missing-path safety). **AC (hard, veto): media proxy validates `file_id` ∈ the resolved level folder (or `missing/`) before streaming — reject unknown ids with 404, no open-proxy for arbitrary public Drive files (R1).** | security-engineer | T5 |
| T6b | **Backend test suite** (pytest + TestClient, Drive mocked): routes, dynamic discovery, missing fallback, theme cookie, error handling. **AC: assert media proxy rejects a `file_id` not in the level/`missing/` folder → 404 (R1); asserts proxy response `Content-Type` mirrors the mocked upstream (R6); asserts missing-level fallback may vary across `/photos` calls and always returns a valid image+audio pair drawn from the mocked `missing/` set (R3).** | qa-tester | T6 |
| T7 | `style.css` dual-theme classes + global theme toggle (cookie + sessionStorage) | frontend-engineer | T5 |
| T8 | `index.html` dynamic Corridor/Island grid | frontend-engineer | T7 |
| T9 | `level.html` room/beach level page + proxied images | frontend-engineer | T7, T5 |
| T10 | Audio crossfade engine (global ⇄ level), auto-play-safe | frontend-engineer | T8, T9 |
| T11 | Security audit of frontend files | security-engineer | T10 |
| T11b | **Frontend/behavioral tests**: SSR theme class per cookie, grid renders configured levels + missing tiles, route smoke checks | qa-tester | T11 |
| T12 | Full suite run + local `uvicorn` smoke test + missing-folder + theme-toggle verification | project-manager | T6b, T11b |
| T13 | Render/Railway deploy config + instructions | project-manager | T12 |

## Gate
✅ **Discovery complete.** All design questions resolved; building with placeholders (`GD_ROOT_FOLDER` + audio stubs filled in locally later). Drive shared public (`GD_API_KEY`); `missing/` folder holds stock images + audio. Phase 2 (`orchestrate-build`) is unblocked — awaiting the user's go to start writing code.

### Risk triage (architect-surfaced)
**Locked by default (no user input required; defaults recommended):**
- R1 — Media proxy MUST validate `file_id` ∈ resolved level/`missing/` folder before streaming; unknown → 404. Hard security AC on T6 (SECURITY_ENGINEER veto).
- R6 — Media proxy echoes upstream Drive `Content-Type`; never hardcodes `image/*`. Hard backend AC on T5.
- R4 — `files.list` handles `pageToken` defensively (loop until no token). Low risk; AC on T5.
- R5 — Empty-but-present numbered folder (zero images) → falls through to missing fallback (treated as not-yet-stocked). AC on T5.
- R2 — ✅ **DECIDED (Q1):** Discovery is startup-built + cached, with a manual `POST /api/refresh` to re-list without a redeploy. No automatic TTL.
- R3 — ✅ **DECIDED (Q2):** Missing-level fallback is **re-rolled on every `/photos` request** — a fresh random image + audio from `missing/` each visit, for a shifting/uncanny effect. No per-level seeding.

**Clarifying questions — RESOLVED:**
1. (R2) Discovery freshness → startup cache + manual `POST /api/refresh` (no automatic TTL).
2. (R3) Missing-level look → re-rolled on each visit (shifting/uncanny), not stable per level.
