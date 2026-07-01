# Knowledge Hub — AI-Driven Commercial Property Underwriting Co-Pilot

This is the **Claude Code knowledge hub** for the project: the context, rules, design, and
backlog that let Claude Code implement the system reliably, ticket by ticket.

## How to use it
1. Copy the **contents** of this hub into your project repo root (so `CLAUDE.md`,
   `.claude/`, and `docs/` sit at the top level).
2. Start Claude Code from the repo root. It auto-loads `CLAUDE.md` and `.claude/rules/`.
3. Tell it to work a ticket, e.g. *"Use the implement-ticket skill to do A1."* It will read
   the ticket, the relevant rules/ADRs, implement, test, and update `docs/PROGRESS.md`.
4. Keep `CLAUDE.md` lean. Deep detail belongs in `docs/`; rules in `.claude/rules/`.

## What's here
```
CLAUDE.md                     Project constitution — invariants + how to work (auto-loaded)
.claude/
  rules/                      Modular, topic-scoped rules
    architecture.md           Service boundaries & ownership
    backend-java.md           Spring Boot orchestrator conventions
    ai-worker-python.md       FastAPI/Ollama worker conventions
    frontend.md               React workbench conventions
    testing-and-commits.md    Test coverage + commit/workflow hygiene
  skills/                     Procedural playbooks (invoked by name)
    implement-ticket/         The standard per-ticket workflow
    run-local-stack/          Local run + demo prep runbook
    add-scoring-factor/       Safe changes to the scoring engine
    add-peril-source/         Add a peril/enrichment source behind the adapter
docs/
  HLD.md                      High-Level Design (the what/why) — Rev 3
  LLD.md                      Low-Level Design (the how) — layout, DDL, classes, algorithm
  MEMORY.md                   Durable knowledge — glossary, invariants, gotchas
  KANBAN.md                   Backlog: epics A–I, sized, dependency-ordered
  PROGRESS.md                 Living checkbox tracker (update as you go)
  adr/                        Architecture Decision Records (0001–0010) + index

# --- A1/A2/A3 starter scaffolding (runnable-but-skeletal) ---
docker-compose.yml            Postgres + RabbitMQ infra (A1)
.env.example                  Copy to .env for compose + local services
backend/                      Spring Boot skeleton: entrypoint, RabbitMQ topology,
                              health stub, empty packages with ticket pointers (A2)
ai-worker/                    FastAPI skeleton: health + startup hooks, config, message
                              schemas, stubbed adapter/consumer/handlers/prompts (A3)
```

## Starter scaffolding (already runnable)
`docker compose up -d` starts the infra. The two service skeletons run (`mvn spring-boot:run`
and `uvicorn app.main:app --port 8001`) and expose health endpoints, but their business
logic is intentionally stubbed with `TODO (<ticket>)` markers so Claude Code fills each
ticket in order. The RabbitMQ topology is fully declared in
`backend/.../messaging/RabbitTopologyConfig.java`. Frontend scaffolding is not included
yet (Epic H) — ask if you want it.

## Reading order for a new contributor (human or AI)
`CLAUDE.md` → `docs/MEMORY.md` (glossary) → `docs/HLD.md` → `docs/LLD.md` →
`docs/KANBAN.md`. Consult `docs/adr/` for the reasoning behind any decision.

## The one-paragraph summary
An underwriter submits a commercial property. A stateless Python/Ollama worker extracts
COPE data and reads photos; Java enriches with real peril data (FEMA/USGS/Nominatim) and
runs a **deterministic** rules engine to produce a versioned, fully-audited
Accept/Refer/Decline recommendation. The AI never decides — it perceives and explains.
Everything runs through an event-driven RabbitMQ pipeline, and every decision is
`AI_PROPOSED` until an underwriter signs off.
