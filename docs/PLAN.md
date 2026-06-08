# Plan & Backlog — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Phase 2 EXECUTION COMPLETE — M1–M7 done, M8 (live deploy) pending. NEW: M9 Horror Atmosphere Redesign (frontend-only visual restyle) in Discovery — see bottom section.** Backend + frontend implemented, security-audited (T6/T11 APPROVED), full pytest suite green (58 passed, 0 warnings), local `uvicorn` smoke test passing, deploy config (`render.yaml` + `Procfile`) committed. R2/R3 decisions locked (see Risk triage). Remaining: provide real `GD_API_KEY`/`GD_ROOT_FOLDER` + assets, then live verification on Render/Railway.

## Milestones
- [x] **M0 — Discovery:** dual-theme PRD captured; requirements, architecture, plan documented; design questions answered.
- [x] **M1 — Scaffold & secure:** PRD file tree (`app/`, `static/`, `templates/`), `requirements.txt`, `.env.example` (`GD_API_KEY`, `GD_ROOT_FOLDER`), hardened `.gitignore`, audio tree `static/audio/{global,horror,sea}/` (missing-level fallback audio is from Drive `missing/`, not local — D6/D9).
- [x] **M2 — Backend dynamic core:** `drive_service.py` (Drive client under `GD_ROOT_FOLDER`, child discovery for dynamic scaling, `missing/` image fallback), `main.py` routes incl. theme cookie.
- [x] **M3 — Theme system:** `style.css` `.theme-horror`/`.theme-sea`, global toggle on every page, cookie + sessionStorage persistence, SSR theme read.
- [x] **M4 — Landing grid:** dynamic Corridor Grid ⇄ Island Map; renders configured levels + missing tiles.
- [x] **M5 — Level pages:** `/level/{id}` (`level.html`) room/beach presentation; image rendering via proxy.
- [x] **M6 — Audio engine:** global ambient per theme + per-level crossfade, auto-play-safe.
- [x] **M7 — Harden, test & verify:** error handling, missing-folder paths, security audit per file (T6/T11 APPROVED), **QA_TESTER pytest suite (Drive mocked) + behavioral checks — 58 passed, 0 warnings**, local `uvicorn` smoke test (`/`, `/api/levels`, theme cookie all 200; graceful degradation with no GD env). All units frozen post-audit + green tests.
- [ ] **M8 — Deploy:** Render/Railway config committed (`render.yaml` Blueprint + `Procfile`), `GD_API_KEY`/`GD_ROOT_FOLDER` env vars documented; **live verification pending**.

> **Two-layer `available` semantics (QA-flagged, by design):** `/api/levels` reports `available` = the numbered Drive folder *exists*; `/api/levels/{id}/photos` reports `available` = the folder exists **and** is non-empty. A level can be listed as available yet still serve the `missing/` fallback when its photos are fetched.

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
✅ **Discovery complete** and ✅ **Phase 2 execution complete.** All units built, audited (T6/T11), and verified (58 tests green + uvicorn smoke). Built with placeholders (`GD_ROOT_FOLDER` + audio stubs filled in locally later). Drive shared public (`GD_API_KEY`); `missing/` folder holds stock images + audio. Remaining gate: **M8 live deploy** — user supplies real credentials/assets, then verify on Render/Railway.

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

---

## Horror Atmosphere Redesign (change request — 2026-06-08)

Status: **Discovery COMPLETE — design approved (ARCHITECTURE §8), decisions LOCKED, ready for `orchestrate-build`.** Frontend-only visual restyle of the HORROR theme (REQUIREMENTS §9, HR1–HR8 / NF-HR1–NF-HR6). Sea & Island, backend, routes, payloads, audio, and deploy config are all out of scope and unchanged. Architect surfaced 6 technical risks (R-H1…R-H6, ARCHITECTURE §8.9) — all folded into the backlog ACs below.

**User-locked decisions (2026-06-08):**
- HQ1 — Background technique: **pure CSS/SVG** (no raster asset; H5 skipped).
- HQ2 / R-H1 — Cloaked hooded figure: **INCLUDED** (user override of the OFF default) — must be tuned (low opacity, anchored low-center) so it does not clutter or sit under the door grid.
- HQ3 / R-H6 — Per-level page intensity: **FULL corridor scene** behind the slideshow (user override of the calmer default) — so R-H5 glow-wash guard + R-H2 contrast check over the slideshow are now critical, not optional.
- HQ4 — Ambient motion: **ON, subtle**, frozen under `prefers-reduced-motion`.

### Milestone
> **⚠️ Shipped design (2026-06-09) diverged from the locks above.** HQ1 ("pure CSS/SVG, no raster asset") and HR3 ("keep the door grid, restyle only") were **superseded**: the Horror landing now uses a full-bleed **raster illustrated map** (`static/img/horror/landing-map.v2.jpg`) that *replaces* the door grid, with %-positioned clickable hotspots → `/level/{id}` (`?calibrate` to tune them). Drifting ghosts/silhouettes/fog and the full per-level corridor scene (HQ2/HQ3/HQ4) shipped as planned. Sea theme untouched. See REQUIREMENTS §9.3 note and ARCHITECTURE §8.3 note.

- [x] **M9 — Horror Atmosphere Redesign + landing map (frontend-only):** Cinematic haunted-corridor background on the Horror landing and a horror ambiance behind each per-level stage, via the existing `.atmosphere` overlay + `.theme-horror` `--page-bg-image`/`--vignette` injection points. Door grid layout, all functionality, performance (prefetch/cache), accessibility (`prefers-reduced-motion`), responsiveness, and theme isolation (Sea untouched) all preserved. Security-audited + QA-regression-verified before freeze.

### Sequenced backlog (M9 — after Open Questions resolved)
| # | Task | Owner | Depends on |
|---|---|---|---|
| H0 | Resolve Open Questions HQ1–HQ5 (HQ1 asset strategy, HQ2 decorative scope, HQ3 per-level intensity, HQ4 motion, HQ5 figure/claw page-scope) + architect risk decisions R-H1 (figure on/off) and R-H6 (per-level intensity). All carry recommended defaults (ARCHITECTURE §8.8) — a "go" locks them; only the user-facing subset (see PM Discovery questions) needs an explicit answer. | project-manager + user | §9 |
| H1 | Design technical approach: CSS/SVG vs image-asset vs hybrid; exact `.theme-horror` token changes (navy palette, moonlit `--vignette`/`--page-bg-image`), `.atmosphere` layering plan, responsive `background-size`/position, per-level treatment (HR2). Confirm zero impact to Sea + JS/payloads. **DONE — see ARCHITECTURE §8.1–§8.8.** | solutions-architect | H0 |
| H2 | Implement Horror landing background — restyle `.theme-horror` tokens + atmosphere in `static/style.css` + horror-scoped decorative SVG in `index.html`. Preserve door-grid markup + tile contract (HR3/HR5). **AC (R-H1, LOCKED ON):** the cloaked hooded figure IS included — render it as a faint, low-opacity inline-SVG silhouette anchored low-center behind the grid, `aria-hidden`, `pointer-events:none`; tune opacity/placement so it never obscures or sits under a clickable door tile. Moonlit doorway + faint edge clawed-hands + fog also included. | frontend-engineer | H1 |
| H3 | Implement Horror per-level background — `.theme-horror .level-stage`/page background (HR2); keep slideshow, nav, dots, contrast (HR6) intact. **AC (R-H6, LOCKED — FULL scene):** per-level uses the full corridor scene (glow + fog + figure/claws), NOT the calmer variant. **AC (R-H5, now critical):** because the full scene sits behind the slideshow, keep the `.level-stage` inset shadow AND add a backing scrim/panel behind the images so the central glow + fog never wash out slideshow edges or reduce photo legibility. | frontend-engineer | H1 |
| H4 | Apply chosen decorative elements (moonlit door, figure, clawed hands, fog) per HQ2, and optional reduced-motion-gated ambient motion per HQ4 (HR7/HR8, NF-HR2). **AC (R-H3):** moonlight flicker stays slow/subtle (no rapid luminance flashing, well under 3 flashes/sec) and freezes to a static frame under `prefers-reduced-motion` via an explicit fallback (not the global kill-switch alone). **AC (R-H4):** fog `filter: blur()` kept to small fixed layers; if mobile profiling shows cost, reduce blur radius or bake into the gradient. | frontend-engineer | H2, H3 |
| H5 | (If HQ1 = image/hybrid) Add + optimize background asset(s) under `static/img/horror/`, document source/license; verify byte budget ≤150 KB WebP (NF-HR1). **Skipped under the recommended pure-CSS/SVG default.** | frontend-engineer | H1 |
| H6 | Security audit: confirm diff is restricted to horror-scoped CSS/templates (+ any `static/` asset), no secret/Drive exposure, no open inline-script changes, decorative layers `aria-hidden`. | security-engineer | H2, H3, H4, H5 |
| H7 | QA regression: SSR renders `.theme-horror` from cookie unchanged; **Sea theme byte-unchanged / visually unaffected**; grid renders configured + missing tiles; toggle/nav/slideshow/audio still work; `prefers-reduced-motion` honored; responsive at mobile/desktop; existing pytest suite still green (58). **AC (R-H2):** run a WCAG AA contrast check on `--fg`/`--muted`/`--accent` and slide dots against the new navy `--bg`+fog before freeze; bump `--muted` lightness if it fails. **AC (R-H4):** mobile QA pass confirming no fog-blur jank on a low-end/mobile GPU. | qa-tester | H6 |
| H8 | Local `uvicorn` smoke test (`/`, `/level/{id}`, theme cookie both themes), visual sign-off, confirm no perf regression (prefetch/cache intact). **AC (R-H1):** visual eyeball of the figure decision before sign-off; **AC (R-H5):** confirm level-page glow does not wash the slideshow. | project-manager | H7 |

### Gate (M9)
✅ **Discovery + design complete; H1 done (ARCHITECTURE §8); H0 decisions LOCKED by the user (see status block).** All 6 architect risks (R-H1…R-H6) folded into H2/H3/H4/H7/H8 as acceptance criteria. **Released for `orchestrate-build` Phase 2** (FRONTEND_ENGINEER H2/H3/H4 → SECURITY_ENGINEER H6 → QA_TESTER H7 → PM H8). User chose: pure CSS/SVG, figure INCLUDED, FULL per-level scene, subtle motion. No deploy-config or backend changes; M8 (live deploy) status is independent.
