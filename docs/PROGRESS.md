# Progress Tracker

Living status of the Kanban backlog (`KANBAN.md`). Check the box when a ticket is **Done**
(AC met + tests green + committed). Add a dated one-line note for anything learned or any
follow-up ticket discovered. Update this in the same change that completes a ticket.

_Last updated: 2026-07-01_ — B3 done: full Python consumer (prefetch=1, ack-after-success, app-level retry/DLQ topology), consumer task started in lifespan, 17 new unit tests all green (23 total).

## Sprint 1 — Walking skeleton (async extraction end-to-end)
- [x] A1 · Docker Compose infra
- [x] A2 · Spring Boot skeleton + health
- [x] A3 · FastAPI worker skeleton + health + pre-warm
- [x] A4 · Postgres schema + migrations
- [~] B1 · Queue topology
- [ ] B2 · Java publisher + result listener (idempotent)
- [x] B3 · Python consumer + retry/DLQ
- [ ] C1 · Extraction (text → COPE)

## Sprint 2 — Decision core (real perils + a scored decision)
- [ ] D1 · Nominatim geocoding
- [ ] D2 · FEMA flood + USGS seismic
- [ ] D3 · Mocked hurricane + wildfire
- [ ] E1 · Deterministic scoring engine
- [ ] E2 · Gates
- [ ] E3 · Decision versioning + re-score
- [ ] C2 · Vision analysis

## Sprint 3 — Orchestration + API
- [ ] F1 · State machine + multi-photo join
- [ ] F2 · /evaluate express path
- [ ] F3 · Activity-based watchdog
- [ ] F4 · Event logging across pipeline
- [ ] G1 · Submission + stepwise endpoints
- [ ] G2 · Profile override (PATCH)
- [ ] G3 · Approve + export (gated)
- [ ] C3 · Narrative generation

## Sprint 4 — Frontend + demo
- [ ] H1 · Intake + stepper
- [ ] H2 · COPE review screen
- [ ] H3 · Photos, peril cards, risk dossier
- [ ] H4 · Event timeline + approve/export controls
- [ ] I1 · Synthetic submissions
- [ ] I2 · Seed script + demo runbook

## Notes / learnings
- 2026-07-01 A3: Added pytest test suite (tests/test_health.py + tests/test_llm_adapter.py) + requirements-test.txt; all 6 tests green. FastAPI lifespan replaces deprecated @app.on_event.
- 2026-07-01 B3: Full consumer implemented: prefetch=1, ack-after-success, retryCount < MAX -> uw.retry (TTL), retryCount >= MAX -> FAILURE result + uw.dlx. Consumer task started in FastAPI lifespan. 17 new unit tests; 23 total green.
