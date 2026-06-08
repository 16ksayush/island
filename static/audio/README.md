# static/audio/ — committed audio assets (no Drive, no API key)

All non-fallback audio is served as static files (ARCHITECTURE §6). The audio engine
loops every track (`el.loop = true`) so a track plays continuously until the page
changes or the session ends.

## Layout (real assets in place)

```
static/audio/
├── global/
│   ├── horror_ambient.mp3   # landing-page loop, Horror theme
│   └── sea_ambient.mp3      # landing-page loop, Sea & Island theme
├── horror/
│   └── level_{id}.mp3       # per-level Horror track (one per existing level)
└── sea/
    └── level_{id}.mp3       # per-level Sea track (one per existing level)
```

- **Themes:** `horror` and `sea` (the bright/positive set, sourced from the original
  "light" folder). The frontend requests `/static/audio/{theme}/level_{id}.mp3`.
- **Per-level tracks:** one track per Drive level folder that exists (currently levels
  **1, 2, 8–18**). Each level has a distinct track in both themes. Assignment of a given
  track to a level is arbitrary — rename files to re-map a track to a different level.
- **Adding levels:** if a new numbered folder appears in Drive, drop a matching
  `horror/level_{id}.mp3` and `sea/level_{id}.mp3`. A missing track just plays nothing
  (handled gracefully — no error).

## Missing-level fallback audio is NOT stored here

Per D6/D9/R3, the fallback for an absent Drive level folder is a random image **and** a
random audio re-rolled from the Drive **`missing/`** folder on every `/photos` request —
served via the backend proxy, never from this directory. Leftover stock audio destined
for that Drive folder is staged in the repo-root `drive_missing_upload/` directory
(git-ignored) — upload its contents (plus stock images) to the `missing/` subfolder of
your Drive `GD_ROOT_FOLDER` parent.
