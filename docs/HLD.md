# High-Level Design
## AI-Driven Commercial Property Underwriting Co-Pilot

*Revision 3 — adds the deterministic scoring engine and gate definitions, multi-photo
async join, decision versioning, enrichment threading, activity-based watchdog, and a
Known Limitations section. Builds on Rev 2 (event-driven pipeline, resilience, event
logging, orchestration state machine, human-gate reconciliation).*

---

## 1. Problem Statement

Commercial property underwriting demands greater accuracy amid climate volatility,
inflation, and rising CAT/secondary perils. Traditional physical inspections are slow,
subjective, and expensive, delaying underwriting decisions and missing exposure risks.

This solution enables faster, objective, AI-driven property evaluation — reducing
inspection overhead, reducing loss-ratio leakage, and strengthening underwriting (UW)
discipline through consistent, auditable, explainable decisions.

---

## 2. Design Principles

1. **Defensibility & Auditability** — every decision is reproducible and explainable;
   the same inputs always produce the same score.
2. **Human-in-the-loop** — AI never has final authority. A decision is only *proposed*;
   an underwriter must explicitly approve it before export or action.
3. **Swappable external dependencies** — AI models and peril data sources sit behind
   adapters; mocks/local models are replaced by production sources without touching
   business logic.
4. **Graceful degradation** — an AI/model failure never blocks or corrupts a decision.
5. **End-to-end resilience** — every failure point has a defined outcome: transparent
   retry, partial result with a clear flag, or explicit failure with a reason. No silent
   failures, no corrupted decisions.

**Core stance:** AI is used only for *perception* (reading messy text, reading photos)
and *explanation* (writing the narrative). The risk score and Accept/Refer/Decline
recommendation come from a deterministic rules engine — never from the AI directly.

---

## 3. System Context

```
                     ┌─────────────────────────┐
   Underwriter  ───▶ │   React Frontend (SPA)   │
                     │  polls GET /submissions/{id}
                     └────────────┬────────────┘
                                  │ HTTPS / JSON  (202 Accepted + poll)
                     ┌────────────▼────────────┐
                     │  Java / Spring Boot       │
                     │  Orchestration Service    │  ──JDBC──▶  PostgreSQL
                     │  returns 202 immediately  │             (submissions,
                     │  orchestration state m/c  │              cope_profiles,
                     │  RULES ENGINE (scoring)   │              decisions(versioned),
                     │  calls Nominatim/FEMA/USGS│              task_results,
                     │  (on a bounded executor)  │              event_logs, ...)
                     └──────────┬──────────────┘
                                │ AMQP (publish tasks / consume results + DLQ)
                     ┌──────────▼──────────────┐
                     │   RabbitMQ (broker)       │
                     │   queue.task.text/.vision │
                     │   queue.retry.* (TTL)     │
                     │   queue.result            │
                     │   queue.dlq.text/.vision/.result
                     └──────────┬──────────────┘
                                │ AMQP (prefetch=1 — one task at a time)
                     ┌──────────▼──────────────┐
                     │  Python / FastAPI Worker  │
                     │  single consumer, ack-    │
                     │  after-success; GET /health
                     └──────────┬──────────────┘
                                │
                     ┌──────────▼──────────────┐
                     │   Ollama (local)          │
                     │   llama3.1:8b / 3.2-vision│  ← ONE model at a time
                     └─────────────────────────┘
```

---

## 4. Component Responsibilities

| Component | Owns | Does NOT own |
|---|---|---|
| **React Frontend** | UI flow, overrides, decision approval, export trigger, status/event polling | Business logic, scoring, persistence |
| **Java Orchestration Service** | Public API, submission lifecycle, orchestration state machine, enrichment (Nominatim/FEMA/USGS + mocks), **rules engine / scoring / decision**, persistence, audit + event logging | Calling Ollama, AI prompts |
| **Python AI Worker** | All Ollama calls (extraction, vision, narrative), prompts, JSON parse/retry; own `GET /health` | Decisions, persistence, orchestration, external peril/geocoding calls |
| **RabbitMQ** | Task, retry (TTL), result, and dead-letter queues; durable/persistent | — |
| **PostgreSQL** | All structured state incl. versioned decisions, idempotency records, event logs | — |
| **Ollama (local)** | Llama 3.1 8B (text), Llama 3.2 Vision 11B (vision) | — |

**Health checks:** Java `GET /api/v1/health` verifies Postgres + RabbitMQ + pings the
worker; it does not probe Ollama. The worker's `GET /health` reports Ollama reachability
and model availability.

---

## 5. The Four AI Intervention Points

1. **Intake & Extraction** — submission text → structured COPE, per-field confidence +
   source snippet.
2. **Visual Condition Assessment** — property photo(s) → findings (severity) + a
   condition score.
3. **Peril & Exposure Enrichment** — address → CAT/secondary peril exposure (no LLM;
   real APIs + mocks, see §14).
4. **Decision Narrative** — fixed score + band → plain-language rationale + pricing/ITV
   guidance. Explanatory only; its failure never blocks the decision (§16).

---

## 6. Data Model (Postgres, owned by Java)

```
submissions
  id (uuid, pk), raw_text, status, failure_reason,
  last_activity_at,                  ← drives the activity-based watchdog (§16)
  created_at, updated_at

cope_profiles
  id, submission_id (fk), field_name, value, confidence,
  source_snippet, overridden_by_user (bool), updated_at

photos
  id, submission_id (fk), image_ref, analysis_status,   ← PENDING | DONE | FAILED
  condition_score (nullable), summary (nullable)

photo_findings
  id, photo_id (fk), label, severity, detail

peril_exposures
  id, submission_id (fk), peril, severity, score,
  rationale, is_secondary, source    ← "FEMA NFHL" | "USGS" | "mocked" | "unavailable"

decisions                            ← VERSIONED (never overwritten)
  id, submission_id (fk), version (int), is_current (bool),
  composite_score, recommendation,
  narrative, narrative_source,       ← "ai" | "template-fallback"
  pricing_guidance, exposure_flags (jsonb),
  review_status,                     ← "AI_PROPOSED" | "HUMAN_APPROVED"
  approved_by, approved_at,          ← nullable until sign-off
  created_at

audit_entries
  id, decision_id (fk), factor, impact, explanation   ← ties to a specific version

task_results                         ← idempotency guard (written in the same txn
  id, task_id (uuid, unique),          as the domain rows it protects, §16)
  submission_id (fk), task_type, status, created_at

event_logs                           ← append-only history
  id, submission_id (fk), task_id (nullable),
  event_type, status, actor, detail (jsonb), error_message, created_at
```

Photo binaries stored externally (disk/MinIO); Postgres holds a reference.

**Decision versioning:** each scoring run inserts a new `decisions` row with
`version = max+1` and flips `is_current`. The prior version is retained, so the audit
history distinguishes the AI's original `AI_PROPOSED` recommendation from any post-override
re-score. Approval and export always act on the current version.

**Input validation limits:** `raw_text` ≤ 50 KB; photos JPEG/PNG, ≤ 10 MB each, ≤ 8 per
submission. Enforced at the API boundary; violations return `400`.

**Data-sensitivity note:** Postgres holds confidential commercial data (full submission
text, insured names/addresses, before/after override values). Business-confidential, not
consumer PII; production adds data-at-rest encryption + retention. Deferred consciously.

**Submission status pipeline:**
`DRAFT → PROCESSING → EXTRACTED → REVIEWED → ENRICHED → SCORED → DECIDED → APPROVED`

- Stepwise: `EXTRACTED → REVIEWED` is a human confirm/override.
- `/evaluate` express: that step is automatic, logged `REVIEW_SKIPPED`; the decision is
  `AI_PROPOSED` and still requires sign-off (`DECIDED → APPROVED`) before export.

**Failure statuses:** `FAILED_AI`, `FAILED_ENRICHMENT`, `FAILED_SCORING` (terminal,
retryable via UI).

---

## 7. Public API (Java)

**Async contract:** any endpoint that triggers AI work returns **`202 Accepted`** with
current status; the frontend **polls `GET /api/v1/submissions/{id}`** until a terminal
state. No public endpoint blocks on Ollama.

```
POST   /api/v1/submissions                       create submission                → 201
POST   /api/v1/submissions/{id}/extract          publish extraction task           → 202
PATCH  /api/v1/submissions/{id}/profile          override a field; if a decision
                                                 already exists, supersede it and
                                                 return to REVIEWED (re-score needed)→ 200
POST   /api/v1/submissions/{id}/photos           upload photo + publish vision task→ 202
POST   /api/v1/submissions/{id}/enrich           run enrichment (async, executor)  → 202
POST   /api/v1/submissions/{id}/score            rules engine + publish narrative;
                                                 creates decision version+1        → 202
POST   /api/v1/submissions/{id}/evaluate         one-click end-to-end to an
                                                 AI_PROPOSED decision (review
                                                 auto-skipped + logged)            → 202
POST   /api/v1/submissions/{id}/decision/approve sign off → HUMAN_APPROVED          → 200
GET    /api/v1/submissions/{id}                  full current state (poll target)  → 200
GET    /api/v1/submissions/{id}/events           event-log timeline                → 200
POST   /api/v1/submissions/{id}/export           UW summary (requires HUMAN_APPROVED)→ 200/409
GET    /api/v1/health                            Postgres + RabbitMQ + worker check→ 200
```

- `/evaluate` runs straight through to a **proposed** decision without stopping, but
  never auto-approves; `/export` returns `409` while the current decision is `AI_PROPOSED`.
- **Export contents (MVP: JSON; PDF optional):** final COPE profile, perils with sources,
  the current decision (score, band, recommendation, narrative, pricing guidance,
  exposure flags), the audit trail, the event timeline, and approver/timestamp.

---

## 8. Internal Messaging Contract (Java ↔ Python via RabbitMQ)

Communication is only via RabbitMQ. Python is a pure consumer/publisher (+ `/health`).

**Consumer concurrency invariant:** a **single consumer with `prefetch_count = 1`** —
at most one unacknowledged task at a time. Mandatory: Ollama loads one model at a time,
so concurrency would thrash models; one-in-flight also makes crash recovery trivial.

**Task message:** `{ taskId, submissionId, taskType(EXTRACT|VISION|NARRATIVE), payload, retryCount }`
**Result message:** `{ taskId, submissionId, taskType, status(SUCCESS|FAILURE), payload, errorMessage }`

**Routing:** EXTRACT/NARRATIVE → `queue.task.text` (llama3.1:8b); VISION →
`queue.task.vision` (llama3.2-vision:11b); results → `queue.result`; retries →
`queue.retry.*` (TTL); exhausted → `queue.dlq.*`.

**Retry topology (bounded, corrected):** a plain nack-requeue loops forever, so on
failure the worker: if `retryCount < 3` → re-publish (with `retryCount+1`) to the TTL
**retry queue** (backoff; dead-letters back to the task queue after the delay), then ack;
if `retryCount ≥ 3` → publish to the **DLQ**, then ack. Count is carried in the
application-level `retryCount` (not broker redelivery). Java consumes `queue.result` and
the DLQs.

---

## 9. Orchestration State Machine (Java)

Status-driven and resumable — on restart or via the watchdog, Java re-reads each in-flight
submission and re-issues the next pending action.

| Current | Trigger | Action | Next |
|---|---|---|---|
| `DRAFT` | `/extract` or `/evaluate` | publish EXTRACT; log | `PROCESSING` |
| `PROCESSING` | EXTRACT result | persist COPE (txn+idempotency); log | `EXTRACTED` |
| `EXTRACTED` | human `PATCH /profile` | persist overrides; log `FIELD_OVERRIDDEN_BY_USER` | `REVIEWED` |
| `EXTRACTED` | `/evaluate` express | log `REVIEW_SKIPPED` | `REVIEWED` |
| `REVIEWED` | orchestrator | if any `photos` exist → publish a VISION task per photo; else → enrich | `PROCESSING`/→enrich |
| `PROCESSING` | each VISION result | persist that photo's findings + set `analysis_status=DONE`; **if any photo still PENDING, wait**; else → enrich | (loop)/→enrich |
| →enrich | orchestrator | run enrichment on a **bounded executor** (circuit-breakered); persist perils + sources; log per-source outcomes | `ENRICHED` |
| `ENRICHED` | orchestrator | run **rules engine** (§12); insert decision v+1 (`AI_PROPOSED`) + audit; publish NARRATIVE; log `SCORING_COMPLETED` | `SCORED` |
| `SCORED` | NARRATIVE result | set `narrative`, `narrative_source="ai"`; log | `DECIDED` |
| `SCORED` | NARRATIVE exhausted (DLQ) | templated narrative, `narrative_source="template-fallback"`; log `NARRATIVE_FALLBACK` | `DECIDED` *(never FAILED)* |
| `DECIDED` | `/decision/approve` | set `HUMAN_APPROVED` + approver; log `DECISION_APPROVED` | `APPROVED` |
| `DECIDED`/`APPROVED` | human `PATCH /profile` | mark current decision superseded; log override | `REVIEWED` *(re-score → v+1)* |
| any `PROCESSING` | watchdog (no activity > 15 min) | republish pending task; log `WATCHDOG_REPUBLISHED` | (unchanged) |
| extract/vision | DLQ (retries exhausted) | set `FAILED_AI` + reason (UI: retry or manual COPE entry) | `FAILED_AI` |
| enrich | all APIs down, fallback insufficient | set `FAILED_ENRICHMENT` | `FAILED_ENRICHMENT` |
| scoring | missing prerequisite (no TIV) | set `FAILED_SCORING` | `FAILED_SCORING` |

**Multi-photo join:** the "wait for all vision results" barrier is derived from DB state
(`count(photos where analysis_status='PENDING') == 0`), not an in-memory counter, so it
is idempotent and crash-safe.

---

## 10. End-to-End Sequence (`/evaluate` express path)

```
Frontend        Java (orchestrator)      RabbitMQ         Python worker      Ollama
   │ POST /evaluate  │ publish EXTRACT ─────▶│ (prefetch=1) ───▶│ extract ──▶ 3.1
   │ 202 + poll       │◀── EXTRACT result ────│◀─ ack-after-pub  │◀───────────
   │                 │ persist COPE (txn)     │                  │
   │                 │ log REVIEW_SKIPPED     │                  │
   │                 │ publish VISION×N ─────▶│ ───────────────▶ │ vision ──▶ 3.2-v
   │                 │◀── VISION results ─────│  (join: all DONE)│◀───────────
   │                 │ enrich (executor:      │                  │
   │                 │  Nominatim/FEMA/USGS)  │                  │
   │                 │ RULES ENGINE → decision│                  │
   │                 │  v1 AI_PROPOSED         │                  │
   │                 │ publish NARRATIVE ────▶│ ───────────────▶ │ narrative ▶ 3.1
   │                 │◀── NARRATIVE result ───│                  │◀───────────
   │ DECIDED          │ status=DECIDED         │                  │
   │ (review dossier + timeline)              │                  │
   │ POST /decision/approve → HUMAN_APPROVED  │                  │
   │ POST /export (allowed only now)          │                  │
```

*(Stepwise path is identical except it pauses at `EXTRACTED` for the human `PATCH
/profile`; no `REVIEW_SKIPPED` is logged.)*

---

## 11. Key Business Rules (locked)

- Score + band come from the **deterministic rules engine in Java** (§12), never the LLM.
- A **severe peril** forces at least Refer; **low confidence on a critical field** forces
  at least Refer (gates raise the band **upward only**).
- **Photos optional:** absent → the condition factor is excluded (never defaulted), stated
  in the audit trail. A **hazardous occupancy with no photo** adds a soft `exposure_flags`
  note (does not gate).
- Every decision is **`AI_PROPOSED` until approved**; export is gated on `HUMAN_APPROVED`.
  `/evaluate` may skip mid-pipeline COPE review (logged `REVIEW_SKIPPED`) but never final
  sign-off.
- **Narrative is explanatory only** — its failure yields a templated narrative and the
  decision still stands; never `FAILED_AI`.
- Overriding COPE after a decision **supersedes** it and forces a re-score (new version).
- Every field, factor, override, and approval is captured in the audit trail + event log.

---

## 12. Scoring Engine (deterministic, Java, in-process)

The composite score is **0–100 (higher = riskier)**, produced by a transparent
**additive model**: a baseline plus signed, bounded per-factor contributions, clamped to
[0,100]. Every factor emits one `audit_entries` row (impact + reason), so the score is
fully reconstructable. Factor inputs come only from COPE fields (extracted or
user-overridden), enrichment peril scores, and the vision condition score — never LLM
judgment.

**Baseline:** 20.

| Factor | Contribution |
|---|---|
| Construction — class | Fire-resistive/non-combustible +0 · Masonry non-combustible +4 · Joisted masonry +8 · Frame +15 |
| Construction — year built | ≤10y +0 · 11–30y +5 · 31–50y +10 · >50y +15 · unknown +10 |
| Construction — roof age | ≤5y +0 · 6–15y +5 · 16–20y +10 · >20y +18 · unknown +10 |
| Occupancy — hazard tier | Low +0 · Moderate +6 · Elevated +12 · Hazardous +20 (also sets hazardous flag) |
| Protection — sprinkler | Full NFPA-13 −12 · Partial −6 · None +0 |
| Protection — alarm | Central station −4 · Local/none +0 |
| Exposure — governing peril | round(max peril score × 0.30) |
| Exposure — secondary peril | if a 2nd peril ≥ 60: round(that score × 0.10) |
| Condition — photo present | round(max condition score across photos × 0.15) |
| Condition — no photo | excluded (0), logged |

`composite = clamp(baseline + Σ factors, 0, 100)`

**Bands:** `0–39 Accept · 40–69 Refer · 70–100 Decline`.

**Gates (applied after banding; raise the band upward only):**
- **Severe-peril gate** — any peril of severity *severe* (score ≥ 80) → at least Refer.
- **Low-confidence gate** — any *critical field* with confidence < 0.60 and not
  user-overridden → at least Refer.
- **Missing-prerequisite gate** — missing **TIV** → `FAILED_SCORING` (cannot price);
  other missing critical fields use the conservative "unknown" defaults above and raise
  the low-confidence gate.

**Worked examples**
- *Clean office:* baseline 20, fire-resistive +0, 8y +0, roof 3y +0, office +0, full
  sprinkler −12, central alarm −4, benign peril 30 → +9, condition 15 → +2 = **15 →
  Accept**.
- *Suburban warehouse (no photo):* 20, joisted masonry +8, 25y +5, roof 12y +5, warehouse
  +6, partial sprinkler −6, alarm −4, SCS 58 → +17 = **51 → Refer**.
- *Coastal frame restaurant:* 20, frame +15, 55y +15, roof 22y +18, restaurant +12,
  no sprinkler +0, hurricane 88 → +26, surge 74 → +7, condition 70 → +11 = 124 → clamp
  **100 → Decline** (severe-peril gate independently forces ≥ Refer).

**Definitions**
- **Critical fields:** address, construction_type, occupancy, year_built, total_insured_value.
- **Hazardous occupancies:** commercial cooking/restaurants, auto repair/body, woodworking,
  spray/finishing, flammable/chemical storage, plastics/foam mfg, cannabis cultivation,
  solvent dry cleaning, welding/hot-work.
- **Severe peril:** peril in the *severe* severity band (score ≥ 80).

**Tunability:** these weights/thresholds are a defensible starting calibration meant to be
tuned against historical loss data in production. They live as centralized constants, so
retuning requires no structural change (and keeps scores reproducible per configuration).

---

## 13. AI / Model Layer

- **Ollama**, self-hosted, open-source — cloud-portable, model-agnostic.
- **Llama 3.1 8B** — extraction + narrative. **Llama 3.2 Vision 11B** — photo analysis
  (documented fallback `llava:7b`).
- Feasible on M3 Pro / 18GB; one model loaded at a time, idle models auto-unloaded; the
  worker pre-warms both at startup.
- Single internal LLM adapter in the worker — swapping to Claude/GPT/Gemini needs no
  change to Java or business logic.

---

## 14. Enrichment — Real Data Sources (Decision)

| Peril | Source | Status |
|---|---|---|
| Geocoding | **Nominatim** (≤1 req/sec, `User-Agent`, user-triggered use) | Real |
| Flood zone | **FEMA NFHL** ArcGIS REST (point-in-polygon, returns zone) | Real |
| Earthquake | **USGS Seismic Design Maps** (ASCE 7-22 params) | Real |
| Hurricane/Hail/Wind | NOAA (bulk CSV only) | Mocked |
| Wildfire | USFS / First Street (bulk/paid) | Mocked |

One interface (`lookup(address, occupancy?) -> PerilExposure[]`) regardless of real vs.
mocked; each `PerilExposure` carries a `source` for UI provenance. Real calls have
per-API timeouts + circuit breakers + graceful fallback (§16).

---

## 15. Non-Functional Requirements

| Concern | Approach |
|---|---|
| Explainability | Deterministic scoring (§12) + per-factor audit trail |
| Reproducibility | Same inputs + config → same score |
| Resilience | §16 failure matrix; event-driven pipeline, TTL retries, DLQ, breakers, watchdog |
| Observability | Append-only `event_logs` — every transition, retry, fallback, override, approval |
| Security | Model access server-side only; no PII in app logs; data-at-rest encryption = production (§6) |
| Portability | Containerizable; Postgres + open models avoid lock-in |
| Performance | Async — 202 immediately; model swaps absorbed as queue latency. Serial AI throughput + ~2–3 min express latency: see §18 |

---

## 16. Resilience Design

### Failure-mode matrix

| Failure | Pattern | Outcome |
|---|---|---|
| Message lost in broker | Durable queues + persistent delivery | Survives restart |
| Worker crash | `prefetch=1` + ack-after-success | Unacked task redelivered |
| Ollama timeout/error | Timeout (120s text/180s vision) → app-level retry via TTL queue (max 3) | Then DLQ |
| Bad JSON | One in-worker stricter-prompt retry → retry topology | Second failure → retry/DLQ |
| Extract/Vision exhausted | DLQ → `FAILED_AI` + reason; UI retry or manual entry | Explicit failure |
| **Narrative exhausted** | DLQ → templated narrative; reaches `DECIDED` | *Never* `FAILED_AI` |
| Duplicate result | `task_results` check **inside the write transaction** | Duplicate acked + discarded |
| External API failure | 5s timeout + Resilience4J breaker + fallback | Geocode → keyword; peril → `unavailable` + flag |
| Orchestrator crash | Status pipeline + watchdog | Resume from last status |
| Rules-engine null | Defensive defaults; no TIV → `FAILED_SCORING` | No scoring on incomplete data |
| Unprocessable result | `queue.dlq.result` + alert log | Manual inspection; no poison loop |
| Frontend disconnect | State in Postgres; stateless server | Resume by polling |

### Key patterns
- **`prefetch=1` single consumer** — respects Ollama's one-model constraint; trivial
  crash recovery.
- **Transactional idempotency** — domain rows (COPE/photo/decision) + `task_results` row
  written in **one transaction**, then ack. Crash before commit → no ack → safe redelivery;
  duplicate finds `task_id` present → discarded.
- **App-level TTL retries** — bounded backoff; corrected from naive nack-requeue.
- **DLQ branching** — Java branches on `taskType`: EXTRACT/VISION → `FAILED_AI`;
  NARRATIVE → templated fallback + `DECIDED`.
- **Activity-based watchdog** — republishes only when `last_activity_at` is stale > 15 min.
  Because retries themselves emit events (which refresh `last_activity_at`), an actively
  retrying task never trips it; the 15-min threshold also exceeds the worst-case single-task
  retry envelope (180s × 3 + backoff ≈ 10–11 min). An accidental double-fire is harmless
  (idempotency protects the DB; only a wasted Ollama run).
- **Enrichment on a bounded executor** — external calls (incl. Nominatim's 1 req/sec limit)
  run off the RabbitMQ result-consumer thread so slow lookups don't stall result processing.
- **Circuit breaker (Resilience4J)** per external API; trips after 3 failures, half-opens
  after 30s.
- **Graceful degradation hierarchy** — transparent retry → partial result + visible flag →
  explicit `FAILED_*` + retry. Never silent, never corrupt.
- **Model pre-warm on startup** — cold-load latency paid once, not on the first demo task.

---

## 17. Event Log Design

Append-only `event_logs`: a complete, tamper-evident per-submission history covering
submission lifecycle (created, transitions, `REVIEW_SKIPPED`, export), AI tasks
(published/completed/retry/parse-error/DLQ), human actions (`FIELD_OVERRIDDEN_BY_USER`,
`DECISION_APPROVED`), enrichment (per-API success/fallback/breaker/unavailable), rules
engine (scoring completed, gate triggered, prerequisite missing), infrastructure
(watchdog republish, breaker state).

**UI — live pipeline timeline** (`GET /submissions/{id}/events`), updated on each poll,
showing what happened, when, and by which actor:

```
09:14:02 SYSTEM       Submission created (DRAFT)
09:14:03 SYSTEM       EXTRACT published
09:14:45 AI_WORKER    Extraction completed — 13 fields, 2 low-confidence
09:14:46 SYSTEM       REVIEW_SKIPPED (express)
09:15:44 AI_WORKER    Vision completed — 2 findings (roof wear, debris)
09:15:46 SYSTEM       FEMA NFHL → Zone AE · USGS → SDC D
09:15:46 RULES_ENGINE Scoring completed — composite 74, band Refer (v1, AI_PROPOSED)
09:15:46 RULES_ENGINE Gate: FEMA Zone AE severe → forced Refer
09:16:20 AI_WORKER    Narrative completed → DECIDED
09:17:33 UNDERWRITER  Decision approved → HUMAN_APPROVED
09:17:40 UNDERWRITER  Export generated
```

Schema: `event_logs(id, submission_id, task_id?, event_type, status, actor, detail jsonb,
error_message, created_at)` with indexes on `(submission_id, created_at)` and `task_id`.

---

## 18. Known Limitations (MVP)

- **Serial AI throughput** — `prefetch=1` + one worker + one Ollama means submissions run
  strictly serially through the AI layer; concurrent underwriters queue. Acceptable for the
  MVP; scaling out needs multiple workers/Ollama hosts (which would also relax the
  single-model constraint).
- **End-to-end latency** — an express run is ≈ 2–3 min on the M3 Pro (extraction + two model
  swaps + vision + narrative). Polling UX + startup pre-warm mitigate; it is not instant.
- **Approver identity** — with no authentication (out of scope), `approved_by` is a
  configured/demo actor label, so the "who approved" audit is weaker than production; the
  field and flow are ready for when auth is added.
- **Model-agnostic vs. queue-by-model** — the two task queues are a physical optimization
  for the single-model local Ollama; a single multimodal provider (e.g. Claude) would
  collapse them to one. Logical model-agnosticism is preserved by the adapter boundary —
  the routing is infra, not business coupling.
- **Vision quality** — open vision models are triage-grade, not inspection-grade, at
  fine-grained damage detection.

---

## 19. Explicit Out-of-Scope (MVP)

Live NOAA/wildfire data (bulk/paid; mocked); authentication & roles (the `approved_by`
field anticipates it); portfolio accumulation/bordereaux; regulatory filing; data-at-rest
encryption + retention. Labelled production roadmap, not demo gaps.

---

## 20. Mapping to Capstone Slides

- **Slide 4 (Solution Overview):** §3 + §4 + §13.
- **Slide 5 (Business Flow & Role of AI):** §5 + §9 + §10.
- **Engineering-maturity talking points:** §12 (defensible scoring), §16 (resilience),
  §17 (event-log timeline).

---

## 21. Dependencies

**Infra:** Ollama; PostgreSQL; RabbitMQ; JDK 17+; Python 3.11+; Node.js+npm; Docker
(recommended); MinIO (optional, production).
**Models (Ollama):** `llama3.1:8b`, `llama3.2-vision:11b` (fallback `llava:7b`); ~12–13GB
combined at Q4; feasible on M3 Pro/18GB.
**Java:** `spring-boot-starter-web`, `-data-jpa` + `postgresql`, `-validation`,
`-amqp`, `WebClient`/`RestClient`, `resilience4j-spring-boot3`, `springdoc-openapi`
(optional).
**Python:** `fastapi`, `uvicorn`, `ollama`, `aio-pika`, `pydantic`, `python-multipart`.
**Frontend:** `react`, `vite`, `tailwindcss`, `axios`/`fetch`, `@tanstack/react-query`.
**External free APIs (from Java):** Nominatim (geocoding), FEMA NFHL (flood), USGS Seismic
Design Maps (earthquake).
