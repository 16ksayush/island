# static/audio/ — committed audio assets (no Drive, no API key)

All audio is served as static files (ARCHITECTURE §6). The `.mp3` files here are
**0-byte placeholders / stubs** for scaffolding (T1) — drop in the real tracks later.

Layout:
- `global/horror_ambient.mp3`, `global/sea_ambient.mp3` — landing-page looping ambient, one per theme.
- `horror/level_{id}.mp3`, `sea/level_{id}.mp3` — per-level track, per theme. Only a couple of
  placeholders (`level_1`, `level_2`) are committed; add `level_0 … level_18` per theme as real audio arrives.

Note: missing-level fallback audio is NOT stored here — it is re-rolled from the Drive `missing/`
folder on every `/photos` request (ARCHITECTURE §6, D6/D9; R3).
