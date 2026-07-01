# Kanban Backlog

Board columns: `Backlog → Ready → In Progress → In Review → Testing → Done`.
Work top-to-bottom respecting **dependencies**. Suggested WIP limit: 2–3 per column.
Sizes: S ≈ ½ day · M ≈ 1–2 days · L ≈ 3+ days. Status is tracked in `PROGRESS.md`.
Each ticket: use the `implement-ticket` skill. AC = acceptance criteria.

Estimation note: C1–C3 (prompt-dependent AI work) need iteration; treat estimates loosely.

---

## Epic A — Foundation & Infra

### A1 · Docker Compose infra · S · deps: none
As a developer, I want one-command local infra so the team shares identical services.
- AC: `docker compose up -d` starts Postgres + RabbitMQ (and MinIO if enabled).
- AC: RabbitMQ queues + DLQ + retry topology declared durable on startup.
- AC: healthchecks defined; management UI reachable.

### A2 · Spring Boot skeleton + health · S · deps: A1
- AC: runnable Spring Boot app; `GET /api/v1/health` checks Postgres + RabbitMQ + worker ping.
- AC: package layout per `LLD §1`.

### A3 · FastAPI worker skeleton + health + pre-warm · M · deps: A1
- AC: FastAPI app with `GET /health` reporting Ollama reachability + models present.
- AC: startup pre-warms `llama3.1:8b` and `llama3.2-vision:11b`.
- AC: connects to RabbitMQ with `prefetch_count=1`.

### A4 · Postgres schema + migrations · M · deps: A2
- AC: all tables from `LLD §2` created via migration (Flyway/Liquibase).
- AC: versioned-decision constraint (`one_current_decision`) + event-log indexes present.

---

## Epic B — Messaging Backbone

### B1 · Queue topology · M · deps: A1, A3
- AC: `task.text/vision`, `retry.*` (TTL), `result`, `dlq.*` declared + bound (HLD §8).

### B2 · Java publisher + result listener (idempotent) · M · deps: A4, B1
- AC: publishes TaskMessage (LLD §3); `ResultListener` is `@Transactional`, idempotent via
  `task_results`; acks after commit; writes event log.

### B3 · Python consumer + retry/DLQ · L · deps: A3, B1
- AC: single `prefetch=1` consumer; ack-after-success; app-level `retryCount` + TTL retry →
  DLQ per ADR-0010; dispatch by taskType.

---

## Epic C — AI Intervention Points

### C1 · Extraction (text → COPE) · L · deps: B2, B3
- AC: returns valid COPE JSON with per-field `confidence` + `source`; never invents values.
- AC: stricter-prompt retry on parse failure; low-confidence fields flagged.

### C2 · Vision analysis (photo → findings) · M · deps: B2, B3
- AC: structured findings with severity + condition score; graceful "unclear/not a building".

### C3 · Narrative generation · M · deps: E1
- AC: prose rationale + pricing guidance from the fixed score; template fallback on failure
  (reaches `DECIDED`, never `FAILED_AI`).

---

## Epic D — Enrichment

### D1 · Nominatim geocoding (executor + breaker + rate limit) · M · deps: A2
- AC: address → lat/lon; keyword fallback on failure; ≤1 req/sec; descriptive User-Agent.

### D2 · FEMA flood + USGS seismic lookups · M · deps: D1
- AC: point lookups → `PerilExposure` with `source`; `unavailable` + exposure flag on failure.

### D3 · Mocked hurricane + wildfire · S · deps: D1
- AC: same `PerilSource` interface; `source="mocked"`; consistent severity banding.

---

## Epic E — Decision Core

### E1 · Deterministic scoring engine · L · deps: A4
- AC: additive model (LLD §6); clamp; bands; one audit entry per contributing factor.
- AC: unit-tested against the three worked examples (HLD §12) + determinism test.

### E2 · Gates · M · deps: E1
- AC: severe-peril and low-confidence gates raise band upward only; missing TIV →
  `FAILED_SCORING`; hazardous-occupancy-no-photo soft flag.

### E3 · Decision versioning + re-score-on-override · M · deps: E1, G2
- AC: new version per score, `is_current` flip; override supersedes + returns to `REVIEWED`.

---

## Epic F — Orchestration & Resilience

### F1 · State machine + multi-photo join · L · deps: B2, C1, C2, D2, E2
- AC: implements HLD §9 transitions; DB-derived photo barrier; resumable from status.

### F2 · /evaluate express path · M · deps: F1, C3
- AC: runs end-to-end to `AI_PROPOSED`; logs `REVIEW_SKIPPED`; never auto-approves.

### F3 · Activity-based watchdog · M · deps: F1
- AC: republishes tasks when `last_activity_at` stale > 15 min; idempotent; won't fire mid-retry.

### F4 · Event logging across pipeline · M · deps: B2
- AC: append-only rows for every event type in HLD §17; `/events` endpoint returns timeline.

---

## Epic G — Public API & Human-in-the-loop

### G1 · Submission + stepwise endpoints (202 + poll) · M · deps: B2
- AC: create/extract/photos/enrich/score endpoints per HLD §7; validation limits enforced.

### G2 · Profile override (PATCH) · S · deps: G1
- AC: edits a field with `overridden_by_user=true`; logs `FIELD_OVERRIDDEN_BY_USER`.

### G3 · Approve + export (gated) · M · deps: F2, G1
- AC: `/decision/approve` → `HUMAN_APPROVED`; `/export` returns 409 while `AI_PROPOSED`;
  export contents per HLD §7.

---

## Epic H — Frontend Workbench

### H1 · Intake + stepper · M · deps: G1
- AC: submit raw text; workbench with the pipeline stepper; polls status.

### H2 · COPE review screen (human gate) · L · deps: H1, C1, G2
- AC: per-field confidence + source snippet; inline edit → `PATCH /profile`.

### H3 · Photos, peril cards, risk dossier · L · deps: H1, C2, D2, E1
- AC: photo upload + findings; peril cards with `source`; dossier (score, band, audit,
  narrative, pricing, flags).

### H4 · Event timeline + approve/export controls · M · deps: H1, F4, G3
- AC: live timeline from `/events`; approve button; export disabled until `HUMAN_APPROVED`.

---

## Epic I — Demo readiness

### I1 · Synthetic submissions · S · deps: none
- AC: low/medium/high-risk sample submissions (+ optional photos) covering Accept/Refer/Decline.

### I2 · Seed script + demo runbook · S · deps: I1, F2
- AC: script seeds demo data; runbook covers model pre-warm + the showcase flow.
