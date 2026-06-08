# 🗝️ Archive 19 — Dual-Atmosphere Dynamic Gallery

An interactive web gallery with a **dynamically-scaled** number of levels (0 → up to 18), presented through **two distinct, toggleable realities**. The chosen theme persists across the whole session and can be switched from any page.

| THEME A — 🕯️ Horror | THEME B — 🏝️ Sea & Island |
|---|---|
| Haunted Gothic Corridor — levels are *doors / rooms* along an eerie hallway | Sunlit Archipelago Map — levels are *islands* across an open ocean |
| `#0D0D0D` obsidian + `#FFB000` molten amber, shadowed vignette | `#E0F2FE`/`#0284C7` azures + warm sand, white coral, palm green |
| Continuous atmospheric horror soundtrack | Bright, relaxing ocean/acoustic ambient |

> **Status:** 🏗️ Blueprint complete (Discovery ✅). The full design — requirements, architecture, and build plan — is locked. Application code is generated in Phase 2 via the `orchestrate-build` multi-agent skill. See [Project Status](#-project-status).

---

## ✨ Features

- **Dual, toggleable themes** — Horror and Sea & Island, swapped from a control on *every* page.
- **Session-persistent theme** — stored via cookie + `sessionStorage`; SSR reads the cookie for a flash-free first paint (default: Horror).
- **Dynamic level discovery** — the grid sizes itself to whatever numbered folders exist in Google Drive (5, 12, 19… all work).
- **Per-level pages** at `/level/{id}`, styled as a *room* (Horror) or a *beach* (Sea).
- **Secure image proxy** — level images are fetched from Google Drive and streamed as bytes by the backend; the browser **never** receives the Google Drive API key.
- **Missing-level fallback** — if a numbered folder is absent, the backend serves 1 random image **and** 1 random audio track from the Drive `missing/` folder.
- **Audio crossfade engine** — landing-page global ambient fades out while a per-level track fades in (and back), auto-play-safe.

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Backend | **FastAPI** + **Uvicorn**, **Jinja2** SSR, **httpx** (Drive client) |
| Frontend | Semantic HTML5, **Tailwind CDN** + custom `style.css` (`.theme-horror` / `.theme-sea`), native `<audio>` |
| Media | Images → **Google Drive** (proxied); audio → **GitHub repo** (`static/audio/`, served static) |
| Hosting | Render / Railway (free tier), secrets via environment variables |

---

## 🏛️ Architecture (overview)

```
Browser (corridor grid / island map)
   │  GET /level/{id}  (SSR page)          │  GET /api/levels/{id}/photos
   ▼                                        ▼
FastAPI (app/main.py) ── reads theme cookie ── renders level.html
   │
   ▼ app/drive_service.py ──GD_API_KEY (os.environ)──► Google Drive API (under GD_ROOT_FOLDER)
        • list parent's children → discover which levels exist (dynamic scaling)
        • folder {id} present → list its images
        • folder {id} ABSENT  → 1 random image + 1 random audio from `missing/`
   ▼
Browser proxies image bytes via /api/levels/{id}/media/{file_id}; never sees the key.
Audio loads from /static/audio/...  (no Drive, no key).
```

### Planned endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Landing page; dynamic grid sized to configured levels; theme from cookie |
| GET | `/level/{id}` | Dedicated, theme-styled level page (room / beach) |
| GET | `/api/levels` | Configured levels + availability flag (real vs missing-fallback) |
| GET | `/api/levels/{id}/photos` | Image refs for a level (proxied URLs) |
| GET | `/api/levels/{id}/media/{file_id}` | Stream a single image's bytes from Drive |

Full design lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), and [docs/PLAN.md](docs/PLAN.md).

### Planned project structure

```
island/
├── app/
│   ├── main.py            # routes, theme cookie, dynamic level loop, Jinja2
│   └── drive_service.py   # Drive client, child discovery, missing/ fallback
├── static/
│   ├── style.css          # .theme-horror / .theme-sea
│   └── audio/
│       ├── global/        # horror_ambient.mp3, sea_ambient.mp3
│       ├── horror/        # level_0.mp3 … level_18.mp3
│       └── sea/           # level_0.mp3 … level_18.mp3
├── templates/
│   ├── index.html         # landing: Corridor Grid ⇄ Island Map
│   └── level.html         # level page: room ⇄ beach by theme
├── docs/                  # REQUIREMENTS · ARCHITECTURE · PLAN
├── requirements.txt       # fastapi, uvicorn, jinja2, httpx
├── .env.example           # GD_API_KEY= , GD_ROOT_FOLDER=
└── render.yaml / Procfile
```

---

## ⚙️ Configuration

The app reads two environment variables (never commit the key):

| Variable | Type | Description |
|---|---|---|
| `GD_API_KEY` | **secret** | Google Drive API key. Read via `os.environ`; kept server-side only. |
| `GD_ROOT_FOLDER` | config | ID/link of the parent Drive folder whose children are the numbered subfolders `0..18` + `missing/`. |

> The parent Drive folder must be shared **"Anyone with the link → Viewer"** so a plain API key can read it. Copy `.env.example` to `.env` and fill in your values.

---

## 🚀 Getting Started

> ⚠️ Application code is produced in Phase 2 (see [Project Status](#-project-status)). Once `app/`, `requirements.txt`, and `.env.example` exist, the steps below apply.

```bash
# 1. Clone
git clone https://github.com/16ksayush/island.git
cd island

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets
cp .env.example .env             # then fill in GD_API_KEY and GD_ROOT_FOLDER

# 5. Run the dev server
uvicorn app.main:app --reload
```

Open http://localhost:8000.

---

## 🤖 How this project is built (Claude Code)

This repo is engineered with [Claude Code](https://claude.com/claude-code) using a multi-agent workflow. Five engineering personas are implemented as **subagents** (`.claude/agents/`), coordinated by **skills** (`.claude/skills/`):

| Subagent | Role |
|---|---|
| 👔 `project-manager` | Init, roadmap, task checklists, deployment |
| 📐 `solutions-architect` | Route signatures, payloads, level → Drive-folder schema |
| ⚙️ `backend-engineer` | FastAPI/Uvicorn + httpx Drive proxy |
| 🎨 `frontend-engineer` | Semantic HTML, Tailwind grid, themes, audio engine |
| 🛡️ `security-engineer` | Credential isolation, `.gitignore` policy, per-file audit |
| 🧪 `qa-tester` | pytest + FastAPI TestClient (Drive mocked) + smoke checks |

**To build:** run the `orchestrate-build` skill (or ask the `project-manager` agent to start). It runs Phase 1 (Discovery & Blueprinting) and Phase 2 (Autonomous Execution) with explicit hand-offs. See [CLAUDE.md](CLAUDE.md) for the full blueprint.

---

## 📊 Project Status

Discovery is **complete**; build proceeds with placeholders. Milestones:

- [x] **M0 — Discovery** — dual-theme PRD, requirements, architecture, and plan documented
- [ ] **M1 — Scaffold & secure** — file tree, `requirements.txt`, `.env.example`, hardened `.gitignore`, audio tree
- [ ] **M2 — Backend dynamic core** — `drive_service.py`, `main.py` routes + theme cookie
- [ ] **M3 — Theme system** — `style.css`, global toggle, cookie + sessionStorage, SSR theme read
- [ ] **M4 — Landing grid** — dynamic Corridor Grid ⇄ Island Map
- [ ] **M5 — Level pages** — `/level/{id}` room/beach presentation + proxied images
- [ ] **M6 — Audio engine** — per-theme ambient + per-level crossfade
- [ ] **M7 — Harden, test & verify** — error handling, pytest suite (Drive mocked), local smoke test
- [ ] **M8 — Deploy** — Render/Railway config, live verification

---

## 🔐 Security

- `GD_API_KEY` is read only from the environment and **never** leaves the server — the browser proxies image bytes through the backend.
- `.env` is git-ignored; only `.env.example` (with empty fill-in stubs) is committed.
- Every file is audited by the `security-engineer` agent before it is frozen.

---

## 📄 License

No license has been specified yet.
