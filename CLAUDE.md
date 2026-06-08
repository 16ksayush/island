# Master Blueprint: Archive 19 — Dual-Atmosphere Dynamic Gallery (Claude Code Edition)

## 🎯 Core Objective
Build a **dynamically-scaled** level gallery (0 → up to 18) with **two toggleable themes** whose selection persists for the session, using a Python backend. See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PLAN.md](docs/PLAN.md) for the authoritative spec.
- **Dual theme:** **Horror** (Haunted Corridor — `#0D0D0D`/`#FFB000`, levels are doors/rooms) and **Sea & Island** (sunlit Archipelago — azures/sand, levels are islands). Toggle on every page; persisted via cookie + sessionStorage (SSR reads the cookie; default Horror).
- **Frontend:** SSR Jinja2 templates (`index.html` grid, `level.html` per-level page at `/level/{id}`), Tailwind CDN + `style.css` (`.theme-horror`/`.theme-sea`), and an audio crossfade engine (theme global ambient ⇄ per-level track).
- **Backend:** FastAPI proxy that fetches media bytes from per-level Google Drive folders (key never leaves the server). Dynamic level discovery; if a numbered folder is missing, a `missing/` folder supplies 1 random image + 1 random audio.
- **Hosting Target:** Free deployment on Render or Railway using environment variables for secrets (`GD_API_KEY`).

---

## 🛠️ How this project is structured for Claude Code

The five engineering personas are implemented as **subagents** (each with its own context window and scoped tools), and the orchestration flow is a **skill**. Invoke the skill to build the project; it dispatches the subagents with explicit hand-offs.

### Agent profiles → subagents (`.claude/agents/`)
| Persona | Subagent | Role |
|---|---|---|
| 👔 PROJECT_MANAGER | `project-manager` | Init, roadmap, task checklists, deps, deployment. Authorized for `mkdir`/`touch`/`pip`/`git`. |
| 📐 SOLUTIONS_ARCHITECT | `solutions-architect` | Route signatures, payloads, level→Drive-folder-ID schema. FastAPI + Jinja2 SSR or static + `/api/levels/{id}/photos`. |
| ⚙️ BACKEND_ENGINEER | `backend-engineer` | FastAPI/Uvicorn + `requests`/`httpx` Drive proxy. `try-except` I/O, secrets via `os.environ.get()`. |
| 🎨 FRONTEND_ENGINEER | `frontend-engineer` | Semantic HTML5, Tailwind CDN grid, Gothic theme, 1.5s CSS transitions, defensive `.mp3` audio. |
| 🛡️ SECURITY_ENGINEER | `security-engineer` | Zero-trust credential isolation, `.gitignore` policy, per-file audit. **Veto power** over secret exposure. |

### Orchestrator (`.claude/skills/orchestrate-build/`)
The `orchestrate-build` skill emulates an internal state machine, transferring control between personas using the hand-off syntax:

```
>>> [AGENT_NAME] INITIALIZED >>>
[persona-specific actions, shell commands, or file edits]
<<< [AGENT_NAME] TERMINATED -> CALLING [NEXT_AGENT_NAME] <<<
```

- **📡 Phase 1 — Discovery & Blueprinting:** PM scaffolds → ARCHITECT designs → SECURITY_ENGINEER audits + creates `.gitignore` → PM returns a Discovery Report with clarifying questions.
- **🔨 Phase 2 — Autonomous Execution:** PM compiles + sequences the backlog → BACKEND_ENGINEER & FRONTEND_ENGINEER write files → SECURITY_ENGINEER audits every change before freeze → PM runs the local `uvicorn` test and produces deployment instructions.

**To build:** run the `orchestrate-build` skill (or ask the PM agent to start Phase 1).
