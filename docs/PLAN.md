# Plan & Backlog — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Phase 2 EXECUTION COMPLETE — M1–M7 done, M8 (live deploy) pending. M9 Horror Atmosphere Redesign + landing map SHIPPED (2026-06-09). M10 Sea (Light) landing map (frontend-only) — BUILT + SECURITY-APPROVED + QA-VERIFIED, pending commit (2026-06-09) — see bottom section. After M9+M10 both themes are map-based.** Backend + frontend implemented, security-audited (T6/T11 APPROVED), full pytest suite green (**140 passed**, 0 failures), local `uvicorn` smoke test passing, deploy config (`render.yaml` + `Procfile`) committed. R2/R3 decisions locked (see Risk triage). Remaining: provide real `GD_API_KEY`/`GD_ROOT_FOLDER` + assets, then live verification on Render/Railway.

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

---

## M10 — Sea (Light) landing map (change request — 2026-06-09)

Status: **Discovery COMPLETE — requirements captured (REQUIREMENTS §10, SR1–SR9 / NF-SR1–NF-SR6), technical design AUTHORED (ARCHITECTURE §9.1–§9.9), architect defaults LOCKED, USER SIGN-OFF received (2026-06-09): art used as-is for the Sea/light theme, names in aria-label, no mobile grid fallback. Released for `orchestrate-build` Phase 2.** Frontend-only redesign of the SEA (light) theme landing: replace the dynamic island grid with a full-bleed illustrated archipelago map (`static/img/light/landing-map.png`, optimized to `landing-map.v2.webp` ≤400 KB before ship) + 19 %-positioned hotspots → `/level/{id}`, mirroring the shipped M9 Horror map. Horror theme, backend, routes, payloads, audio, and deploy config are out of scope and unchanged.

### Milestone
- [x] **M10 — Sea (Light) landing map (frontend-only) — BUILT + SECURITY-APPROVED + QA-VERIFIED (full suite 140 passed / 0 failed); pending commit (PM S8 done):** Full-bleed illustrated archipelago map on the Sea landing replacing the dynamic island grid, with 19 calibrated %-positioned clickable hotspots → `/level/{id}` and sealed/sunken styling for unavailable levels. Theme toggle overlaid (clear of the painted pill), keyboard-accessible hotspots with name-aware aria-labels, optimized image (`landing-map.v2.webp`, 214 KB) within byte budget, `prefers-reduced-motion` honored, responsive mobile→desktop. Horror landing byte-unchanged; security-audited + QA-regression-verified.

### Open Questions — resolution state (full text in REQUIREMENTS §10.5 / ARCHITECTURE §9.8)
**Architect-LOCKED-on-go (no user input needed):**
- **SQ1** class strategy → reuse shared `.map-hotspot*` leaf classes both themes + Sea-scoped `.sea-map*` containers; NO macro, NO Horror rename (§9.2).
- **SQ2** image → single WebP `landing-map.v2.webp`, q≈80, ~1600px, ≤400 KB (ceiling 600 KB) (§9.4).
- **SQ4** ambient → off by default; `.sea-ambient` hook documented (§9.6).
- **SQ5 (scale/pan model)** → scale-to-fit + letterbox desktop, pan-to-fit mobile, no grid fallback (§9.5).

**RESOLVED by user sign-off (2026-06-09):**
- **SQ6** → ✅ art used for the Sea & Island (light) theme **as-is**; Sea keeps its sunlit azure palette + "Enter the Corridor"/🌙 copy. Painted location names treated as island names, not a horror restyle.
- **SQ3** → ✅ names exposed in `aria-label` only ("Level 5 — Prison"); visible UI numbers-only.
- **SQ5 sub-question** → ✅ NO mobile island-grid fallback; map scales/pans to fit on all sizes; grid markup deleted.

### Sequenced backlog (M10 — decisions LOCKED; tasks reflect ARCHITECTURE §9)
| # | Task | Owner | Depends on |
|---|---|---|---|
| S0 | **Sign-off gate.** Architect defaults are LOCKED (SQ1/SQ2/SQ4/SQ5-model). Obtain the explicit USER answer to **SQ6** (art-for-Sea as-is + azure palette/copy kept + eerie names in aria vs suppressed → resolves SQ3) and the **SQ5 sub-question** (mobile grid fallback? default NO). A simple "go with defaults" satisfies all of these. R-S1/R-S4/R-S6 closed-or-mitigated; R-S2/R-S3/R-S5/R-S7/R-S8 carried as ACs below. **✅ DONE — user sign-off 2026-06-09 (art as-is, names in aria-label, no mobile grid fallback).** | project-manager + user | §10, §9 |
| S1 | **Technical design — DONE (ARCHITECTURE §9.1–§9.9).** Class strategy (§9.2 SQ1), `sea_coords`+`sea_names` source (§9.3), image opt spec (§9.4 SQ2), responsive plan (§9.5 SQ5), ambient hook (§9.6 SQ4), theme-isolation proof (§9.7 NF-SR4), defaults (§9.8), risks R-S1…R-S8 (§9.9). | solutions-architect | S0 |
| S2 | **✅ DONE.** **Produce the optimized map asset:** `static/img/light/landing-map.v2.webp` from the 2.7 MB `landing-map.png` — WebP q≈82, **1399×768**, **214 KB** (under the ≤400 KB budget); preserve native aspect ratio and **record the exact final WxH** (§9.5 responsive math needs the true ratio). Do NOT ship the raw PNG (retain it only as the design source). Document source/license + optimization origin (R-S2/R-S7, NF-SR1/NF-SR6). | frontend-engineer | S1 |
| S3 | **✅ DONE.** **Sea branch markup** — replaced ONLY the body of the `{% else %}` (Sea) arm in `index.html` (lines ~116–171) with the §9.2 skeleton: `.sea-landing` > `.sea-map` > `.sea-map-img` (`src=".../landing-map.v2.webp"`, `fetchpriority="high"` `decoding="async"`) + `.sea-map-hotspots` looping the inline **`sea_coords`** dict (§9.3) into **shared `.map-hotspot`** anchors (`.map-hotspot-ring`/`.map-hotspot-id`, `.is-sealed` for id ∉ `available_ids`) → `/level/{id}`; `sr-only` `<h1>`; `.sea-map-toggle` overlay. Add the inline `sea_names` dict for aria-labels. **Plus the one-line calibrate-JS change** `document.querySelector(".horror-map")` → `.querySelector(".horror-map, .sea-map")` (§9.2). **Horror arm + shared `.atmosphere` block left byte-identical.** **AC (SQ5 sub, RESOLVED):** delete the Sea grid markup — no mobile grid fallback (user sign-off 2026-06-09). | frontend-engineer | S1, S2 |
| S4 | **✅ DONE.** **Sea map CSS** — NEW block of `.theme-sea .sea-map* { … }` rules in `static/style.css` (parallel to the M9 Horror block): container/img scale-to-fit + letterbox via a Sea-palette `.sea-landing::before` blurred fill (light sky/sand wash, not Horror's storm wash); **shared `.map-hotspot` ring/id/focus styled under `.theme-sea`**; **sealed/"sunken"** styling for unavailable levels (SR5); a Sea-scoped **calibrate twin** (`.theme-sea .sea-map.calibrate …`); Sea mobile breakpoints (pan-to-fit: `.sea-landing` fixed/scroll, `.sea-map-img` 130vw ≤768 / 175vw ≤480, `.map-hotspot` 7% ≤480). **AC (NF-SR4):** every rule prefixed `.theme-sea`; no bare `.map-hotspot{}`; no edit to `.horror-*`, `:root`, shared `html,body`/`.atmosphere`/`.layer`/`.theme-toggle` base. | frontend-engineer | S1 |
| S5 | **✅ DONE.** **Accessibility + toggle + (deferred) decoration** — keyboard-focusable hotspots with name-aware `aria-label`s "Level {id} — {name}" (SR7, SQ3 default), `(sunken — fallback content)` suffix for sealed; decorative layers (`.sea-map-img`, painted-pill region, any ambient) `aria-hidden`+`pointer-events:none`; `.sea-map-toggle` overlaid top-right OVER the painted pill (🌙 "Enter the Corridor", SR6, R-S3). Ambient `.sea-ambient` stays **OFF** (SQ4 default) — hook only. | frontend-engineer | S3, S4 |
| S6 | **✅ DONE — APPROVED.** **Security audit** — confirmed the diff surface is **exactly** {Sea `{% else %}` branch of `index.html` + the one-line calibrate-JS selector, the new `.theme-sea .sea-map*` CSS block, the new `static/img/light/landing-map.v2.webp`} and nothing else; no secret/Drive exposure; no open inline-script changes beyond the documented one-line selector; decorative layers `aria-hidden`; **committed image ≤400 KB (ceiling 600 KB)** (R-S2). Veto on any out-of-scope edit. | security-engineer | S3, S4, S5 |
| S7 | **QA regression** — SSR renders `.theme-sea` map from cookie; **Horror landing byte-unchanged / visually unaffected and Horror `?calibrate` still highlights `.horror-map` (R-S1)**; all 19 hotspots navigate to `/level/{id}`; sealed styling for unavailable ids; **all 19 hotspots reachable on MOBILE incl. bottom-row 12/15/17 via pan-to-fit (R-S8)** and hotspots clear ~44px (R-S5); toggle overlay lands on the painted pill without looking duplicated (R-S3); toggle/nav/slideshow/audio/prefetch still work; `prefers-reduced-motion` honored; WCAG AA contrast on hotspot rings/ids/focus over the bright sunlit art (NF-SR2); committed asset within budget (R-S2); existing pytest suite still green. | qa-tester | S6 |
| S7 | **✅ DONE — VERIFIED.** Added `tests/test_sea_landing.py` (40 tests); reconciled 5 stale grid tests in `tests/test_frontend.py` + `tests/test_horror_atmosphere.py` to the map model. **Full suite 140 passed / 0 failed.** (Row above is the original S7 spec.) | qa-tester | S6 |
| S8 | **✅ DONE.** Completeness check (full suite 140 passed / 0 failed), README + docs synced to the map model (this commit), commit-readiness report produced. No backend/route/payload/audio/deploy change → M8 (Render/Railway) unaffected. Commit is the user's call. | project-manager | S7 |

### Gate (M10)
✅ **BUILT + SECURITY-APPROVED (S6) + QA-VERIFIED (S7, full suite 140 passed / 0 failed) + PM doc-sync done (S8) — pending commit (user's call).** Phase 2 ran end to end: FRONTEND_ENGINEER S2/S3/S4/S5 → SECURITY_ENGINEER S6 → QA_TESTER S7 → PM S8. Risks: R-S1 mitigated (Horror `?calibrate` still highlights `.horror-map`, Horror landing byte-unchanged), R-S2 closed (asset 214 KB ≤ 400 KB budget), R-S4/R-S6 closed. No backend or deploy-config changes; M8 (live deploy) status is independent and unaffected. After M9+M10 both themes are map-based.
