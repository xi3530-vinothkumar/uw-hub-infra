# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project constitution for Claude Code. Kept short on purpose. Deeper material lives in
`docs/` and `.claude/rules/`; read those on demand, not every session.

## What this is
An AI-assisted underwriting workbench for **commercial property (P&C)**. An underwriter
submits a property; the system extracts structured risk data, assesses photos, enriches
with peril/CAT exposure, computes a **deterministic** risk score, and produces an
Accept/Refer/Decline recommendation with a full audit trail. AI never makes the decision.

## Architecture at a glance
- **Frontend** — React + Vite + Tailwind (underwriter workbench, polls for status).
- **Java / Spring Boot** — orchestration service + **system of record**: public API,
  orchestration state machine, **rules engine (scoring)**, enrichment (Nominatim/FEMA/USGS),
  Postgres, audit + event logs. Owns every decision.
- **Python / FastAPI** — stateless **AI worker**: all Ollama calls (extraction, vision,
  narrative). No persistence, no decisions, no external peril calls.
- **RabbitMQ** — async task pipeline (task/retry-TTL/result/DLQ queues).
- **Ollama (local)** — `llama3.1:8b` (text) + `llama3.2-vision:11b` (vision).
- **PostgreSQL** — all structured state.

Full design: `@docs/HLD.md`. Implementation detail: `@docs/LLD.md`.

## Build & test commands

### Infra (Docker — run first)
```
docker compose up -d postgres rabbitmq
```
RabbitMQ management UI: http://localhost:15672 (uw/uwpass)

### Java orchestrator (`backend/`) — port 8080
```bash
# Run
mvn spring-boot:run

# Build (skip tests)
mvn package -DskipTests

# Run all tests
mvn test

# Run a single test class
mvn test -Dtest=RulesEngineTest

# Health check
curl http://localhost:8080/api/v1/health
curl http://localhost:8080/actuator/health
```
No Maven wrapper in the repo — uses the system `mvn` (Java 17 required).

### Python AI worker (`ai-worker/`) — port 8001
```bash
# First-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --port 8001 --reload

# Run tests (once pytest is added in later tickets)
pytest

# Health check
curl http://localhost:8001/health
```

### Frontend (`frontend/`) — port 5173 (not yet scaffolded; arrives in Epic H)
```bash
npm install && npm run dev
```

### Ollama models (pull once)
```
ollama pull llama3.1:8b
ollama pull llama3.2-vision:11b
```

## Codebase map

### Backend packages (`com.uw.copilot.*`)
| Package | Purpose |
|---|---|
| `api` | REST controllers (health; more added per ticket G*) |
| `submission` | Submission domain + JPA entities (ticket A4+) |
| `orchestration` | State machine + multi-photo join (ticket F*) |
| `scoring` | Deterministic `RulesEngine` — pure, side-effect-free (ticket E*) |
| `enrichment` | `PerilSource` port + Nominatim/FEMA/USGS/mocked adapters (ticket D*) |
| `messaging` | `RabbitTopologyConfig` (A1), publisher, `ResultListener` (ticket B2) |
| `common` | Shared DTOs, constants (scoring weights/thresholds live here) |

### Python modules (`ai-worker/app/`)
| Module | Purpose |
|---|---|
| `main.py` | FastAPI app, startup pre-warm, `/health` |
| `config.py` | All config from env vars (queue names, model names, URLs) |
| `consumer.py` | Single `prefetch=1` RabbitMQ consumer (ticket B3) |
| `llm_adapter.py` | Ollama calls — the only place that touches the LLM |
| `schemas.py` | Pydantic message contracts (must match Java `TaskMessage`) |
| `handlers/` | `extract.py`, `vision.py`, `narrative.py` — per-task-type logic (C1–C3) |
| `prompts/` | Prompt templates per task type |

### Queue/exchange names (must stay in sync between Java and Python)
- Exchange: `uw.tasks`, `uw.retry`, `uw.dlx`
- Routing keys: `text`, `vision`, `result`
- Queues: `queue.task.text`, `queue.task.vision`, `queue.result`, `queue.dlq.*`, `queue.retry.*`

Canonical source: `backend/.../messaging/RabbitTopologyConfig.java` and `ai-worker/app/config.py`.

## Non-negotiable invariants (do not violate)
1. **AI perceives and explains; rules decide.** The composite score and band come only
   from the deterministic rules engine in Java. Never let an LLM produce the score.
2. **Python is stateless.** It never touches Postgres, never makes decisions, never calls
   peril/geocoding APIs. It consumes a task, calls Ollama, publishes a result.
3. **Human-in-the-loop.** Every decision is `AI_PROPOSED` until an underwriter approves it.
   Export is gated on `HUMAN_APPROVED`. `/evaluate` may skip mid-pipeline review but never
   final sign-off.
4. **Narrative is cosmetic.** If narrative generation fails, substitute a template and
   still reach `DECIDED`. Narrative failure must never produce `FAILED_AI`.
5. **Single-model worker.** The Python consumer runs `prefetch=1` (Ollama loads one model
   at a time). Never add concurrent consumers.
6. **Everything is auditable.** Every field, factor, override, retry, fallback, and
   approval is recorded (`audit_entries` + append-only `event_logs`). Decisions are
   versioned, never overwritten.
7. **External data is swappable.** Peril sources and the LLM sit behind adapters. Real vs.
   mocked is a config detail; callers must not depend on which.

## How to work here
1. Pick the current ticket from `@docs/KANBAN.md` (respect its dependency order).
2. Read the relevant rule file in `.claude/rules/` and any referenced ADR in `docs/adr/`.
3. Implement to the ticket's acceptance criteria. Make minimal, focused changes.
4. Write/adjust tests. The scoring engine (§12 of the HLD) must be unit-tested against
   its three worked examples.
5. Update `@docs/PROGRESS.md` (check the box, note anything learned).
6. When a real, durable design decision is made or changed, add/update an ADR.

Use the `implement-ticket` skill for the standard per-ticket workflow.

## Conventions
- Language: Java 17 (Spring Boot 3.3) for the orchestrator; Python 3.11 for the AI worker.
- Commit per logical change; conventional-commit style (`feat:`, `fix:`, `docs:`…).
- Don't refactor unrelated code. When two designs are viable, surface both and ask.
- Config/constants centralized (scoring weights, thresholds, model names, queue names).
- Decisions are versioned via `is_current` flip — never update-in-place.
- All external API calls (Nominatim/FEMA/USGS) wrapped with Resilience4J circuit breakers + 5s timeouts + graceful fallback.
