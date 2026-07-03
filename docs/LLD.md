# Low-Level Design (LLD)
## AI-Driven Commercial Property Underwriting Co-Pilot

Implementation-level detail. Pairs with `HLD.md` (the "what/why"); this is the "how".
Read the relevant section before implementing the matching Kanban ticket.

---

## 1. Repository layout

```
repo-root/
  CLAUDE.md
  .claude/{rules,skills}/...
  docs/...
  docker-compose.yml
  backend/                       # Java 17 / Spring Boot (orchestrator)
    src/main/java/com/uw/copilot/
      api/                       # controllers + DTOs
      orchestration/             # state machine, publishers, result/DLQ listeners
      scoring/                   # RulesEngine (pure), constants, gates
      enrichment/                # PerilSource port + adapters, executor, breakers
      submission/                # entities, repositories, services
      messaging/                 # RabbitMQ config, task/result message models
      common/                    # errors, event logging, config
    src/test/java/...
  ai-worker/                     # Python 3.11 / FastAPI (stateless AI worker)
    app/
      main.py                    # FastAPI app + /health + startup pre-warm
      consumer.py                # single prefetch=1 consumer + retry/DLQ logic
      llm_adapter.py             # Ollama access (swappable)
      handlers/{extract,vision,narrative}.py
      prompts/{extract,vision,narrative}.py
      schemas.py                 # pydantic message + payload models
    requirements.txt
  frontend/                      # React + Vite + Tailwind
    src/{components,api,hooks,pages}/...
```

---

## 2. Database DDL (Postgres, owned by Java)

```sql
CREATE TYPE submission_status AS ENUM
  ('DRAFT','PROCESSING','EXTRACTED','REVIEWED','ENRICHED','SCORED','DECIDED','APPROVED',
   'FAILED_AI','FAILED_ENRICHMENT','FAILED_SCORING');

CREATE TABLE submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_text TEXT NOT NULL,
  status submission_status NOT NULL DEFAULT 'DRAFT',
  failure_reason TEXT,
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cope_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES submissions(id),
  field_name VARCHAR(64) NOT NULL,
  value TEXT,
  confidence NUMERIC(3,2),
  source_snippet TEXT,
  overridden_by_user BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (submission_id, field_name)
);

CREATE TABLE photos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES submissions(id),
  image_ref TEXT NOT NULL,
  analysis_status VARCHAR(12) NOT NULL DEFAULT 'PENDING',  -- PENDING|DONE|FAILED
  condition_score INT,
  summary TEXT
);

CREATE TABLE photo_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  photo_id UUID NOT NULL REFERENCES photos(id),
  label TEXT NOT NULL, severity VARCHAR(12) NOT NULL, detail TEXT
);

CREATE TABLE peril_exposures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES submissions(id),
  peril TEXT NOT NULL, severity VARCHAR(12) NOT NULL, score INT NOT NULL,
  rationale TEXT, is_secondary BOOLEAN NOT NULL DEFAULT FALSE, source TEXT NOT NULL
);

CREATE TABLE decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES submissions(id),
  version INT NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  composite_score INT NOT NULL,
  recommendation VARCHAR(8) NOT NULL,          -- Accept|Refer|Decline
  narrative TEXT, narrative_source VARCHAR(20),-- ai|template-fallback
  pricing_guidance TEXT, exposure_flags JSONB,
  review_status VARCHAR(16) NOT NULL DEFAULT 'AI_PROPOSED', -- AI_PROPOSED|HUMAN_APPROVED
  approved_by TEXT, approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (submission_id, version)
);
CREATE UNIQUE INDEX one_current_decision ON decisions(submission_id) WHERE is_current;

CREATE TABLE audit_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id UUID NOT NULL REFERENCES decisions(id),
  factor TEXT NOT NULL, impact TEXT NOT NULL, explanation TEXT NOT NULL
);

CREATE TABLE task_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL UNIQUE,
  submission_id UUID NOT NULL REFERENCES submissions(id),
  task_type VARCHAR(12) NOT NULL, status VARCHAR(8) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE event_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES submissions(id),
  task_id UUID,
  event_type VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL, actor VARCHAR(20) NOT NULL,
  detail JSONB, error_message TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_events_sub ON event_logs(submission_id, created_at);
CREATE INDEX idx_events_task ON event_logs(task_id) WHERE task_id IS NOT NULL;
```

---

## 3. Messaging (RabbitMQ)

**Exchanges/queues:** direct exchange `uw.tasks` → `queue.task.text`, `queue.task.vision`;
`queue.retry.text`/`queue.retry.vision` (per-queue TTL, dead-letter back to task queue);
`queue.dlq.text`/`queue.dlq.vision`; `queue.result` (+ `queue.dlq.result`). All durable,
messages persistent.

**Task message** (`messaging/TaskMessage`): `taskId, submissionId, taskType, payload, retryCount`.
**Result message** (`messaging/ResultMessage`): `taskId, submissionId, taskType, status, payload, errorMessage`.

Payload by type: EXTRACT `{submissionText}`; VISION `{imageBase64, mediaType}`; NARRATIVE
`{profile, perils, photoFindings, compositeScore, band}`.

---

## 4. Java — key components

- **api/SubmissionController** — the endpoints in HLD §7. Triggering endpoints return 202
  and delegate to the orchestrator. Validates input limits.
- **orchestration/OrchestrationService** — the state machine (HLD §9). Methods keyed by
  `(status, event)`; publishes tasks; on result, runs the next step. Uses
  `last_activity_at` bumps on every transition.
- **orchestration/ResultListener** (`@RabbitListener queue.result`) — `@Transactional`:
  check `task_results` for `taskId`; if present → ack+skip; else persist domain rows +
  `task_results` + event log, then advance the state machine. Ack after commit.
- **orchestration/DlqListener** — branches on taskType: EXTRACT/VISION → `FAILED_AI`;
  NARRATIVE → template narrative + `DECIDED`.
- **orchestration/Watchdog** (`@Scheduled`) — republish next task for submissions with
  `last_activity_at` older than 15 min and non-terminal status.
- **scoring/RulesEngine** — pure function `evaluate(profile, perils, photoFindings?) →
  ScoringResult{score, recommendation, auditEntries, exposureFlags}`. No I/O. Algorithm §6.
- **scoring/ScoringConstants** — all weights, band thresholds, `CRITICAL_FIELDS`,
  `HAZARDOUS_OCCUPANCIES`, `SEVERE_PERIL_THRESHOLD=80`, gate config.
- **enrichment/PerilSource** (port) + adapters `NominatimGeocoder`, `FemaFloodAdapter`,
  `UsgsSeismicAdapter`, `MockHurricaneAdapter`, `MockWildfireAdapter`;
  `EnrichmentService` runs them on a bounded `Executor`, each guarded by a Resilience4J
  `@CircuitBreaker` + 5s timeout + fallback.
- **common/EventLogger** — one method to append `event_logs` rows (used everywhere).

---

## 5. Python worker — key components

- **consumer.py** — connects via `aio-pika`, `prefetch_count=1`, subscribes to both task
  queues. For each message: dispatch by taskType → handler; on success publish result +
  ack; on failure apply retry topology (ADR-0010) then ack.
- **llm_adapter.py** — `complete(system, user, model)` and `vision(system, user, image,
  model)`; `complete_json(...)` wraps with fence-stripping + one stricter-prompt retry.
  Model names from env/config. Only file that knows about Ollama.
- **handlers/** — `extract` (text→COPE JSON), `vision` (image→findings JSON), `narrative`
  (context→prose). Each validates output against a pydantic schema before returning.
- **prompts/** — system prompts; must instruct "return ONLY a JSON object", "never invent
  values", per-field confidence + source for extraction.
- **main.py** — FastAPI `/health` (Ollama reachable? models present?) + startup pre-warm.

---

## 6. Scoring algorithm (pseudocode)

```
score = BASELINE (20)
score += construction_class_points(profile.construction_type)
score += year_built_points(profile.year_built)          # unknown → +10
score += roof_age_points(profile.roof_age_years)         # unknown → +10
score += occupancy_points(profile.occupancy)             # sets hazardous flag if hazardous
score += sprinkler_credit(profile.sprinklered)           # negative
score += alarm_credit(profile.alarm)                     # negative
perils_sorted = sort(perils desc by score)
score += round(perils_sorted[0].score * 0.30)            # governing peril
if perils_sorted[1] and perils_sorted[1].score >= 60:
    score += round(perils_sorted[1].score * 0.10)        # secondary peril
if photos_present:
    score += round(max(p.condition_score) * 0.15)
    # else: excluded, add audit entry "not assessed"
score = clamp(score, 0, 100)
band = Accept(0-39) | Refer(40-69) | Decline(70-100)

# gates (raise band upward only)
if any peril.severity == severe (>=80): band = max(band, Refer)
if any critical_field.confidence < 0.60 and not overridden: band = max(band, Refer)
if TIV missing: FAIL -> FAILED_SCORING
if hazardous_occupancy and no photos: add exposure_flag (soft, no gate)

# every contributing factor appends an AuditEntry(factor, impact, explanation)
```

Reference weights and worked examples: `HLD.md` §12. Keep the three worked examples as
unit tests.

---

## 7. Enrichment endpoints (reference)

- **Nominatim:** `GET https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1`
  → `[{lat, lon, ...}]`. Header `User-Agent: uw-copilot/1.0 (contact)`. ≤1 req/sec.
- **FEMA NFHL:** query the NFHL MapServer flood-hazard layer with the point (lat/lon),
  `geometryType=esriGeometryPoint`, `returnGeometry=false`, `f=json`; read the flood zone
  attribute from the returned feature(s).
- **USGS Seismic Design Maps:** point lookup by lat/lon (ASCE 7-22 reference); read seismic
  design category / parameters.
Map each into a `PerilExposure` with a `score` (0–100), `severity` band, and `source`.

---

## 8. Error / exception model

Uniform API error body: `{ error, message, retryable }`. Error codes include
`EXTRACTION_LOW_CONFIDENCE`, `MODEL_UNAVAILABLE`, `PREREQUISITE_MISSING`,
`ENRICHMENT_UNAVAILABLE`, `NOT_APPROVED` (export before sign-off → 409),
`VALIDATION_ERROR` (400). `MODEL_UNAVAILABLE` on `/score` must NOT fail the request — the
rules engine runs without the LLM; only the narrative degrades.

---

## 9. Config / constants (centralized)
- Java: `ScoringConstants`, `MessagingConfig` (queue names/TTLs), `EnrichmentConfig`
  (endpoints, timeouts, breaker settings, Nominatim UA), thresholds (`MIN_FIELD_CONFIDENCE=0.60`).
- Python: env — `OLLAMA_HOST`, `MODEL_TEXT=llama3.1:8b`, `MODEL_VISION=qwen2.5vl:7b`,
  `MAX_RETRIES=3`, queue names.
