# tests/ — pytest + FastAPI TestClient (Drive mocked)

Suite added in T6b / T11b (qa-tester). Covers: routes, dynamic discovery, missing fallback,
theme cookie, error handling. Key ACs:
- media proxy rejects file_id not in level/`missing/` folder -> 404 (R1)
- proxy Content-Type mirrors mocked upstream (R6)
- missing-level fallback may vary across /photos calls; always a valid image+audio pair (R3)
Stub only (T1) — no tests yet.
