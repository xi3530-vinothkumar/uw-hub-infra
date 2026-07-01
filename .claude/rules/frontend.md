# Rule: React frontend

Applies to: `frontend/` (React + Vite + Tailwind).

- The frontend holds no business logic and computes no scores — it renders server state.
- Use the `202 + poll` pattern: after triggering work, poll `GET /submissions/{id}` (and
  `/events` for the timeline) until a terminal status. `@tanstack/react-query` recommended.
- Human-in-the-loop UI is mandatory: the COPE review screen must show per-field confidence
  and the source snippet, and allow editing (which calls `PATCH /profile`).
- The risk dossier must show: composite score, band, per-factor audit trail, narrative,
  pricing guidance, exposure flags, and peril `source` provenance.
- Approve/Export controls: Export is disabled until the decision is `HUMAN_APPROVED`.
- No `localStorage`/`sessionStorage` reliance for source-of-truth state; the server is the
  source of truth.
