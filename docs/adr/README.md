# Architecture Decision Records

Each ADR captures one durable decision: its context, the decision, consequences, and the
alternatives considered. Add a new ADR when a real design decision is made or reversed.
Status values: Accepted · Superseded · Proposed.

| # | Decision | Status |
|---|---|---|
| 0001 | AI perceives & explains; deterministic rules decide | Accepted |
| 0002 | Two services: Java orchestrator + Python AI worker | Accepted |
| 0003 | Local Ollama models, model-agnostic via adapter | Accepted |
| 0004 | Event-driven pipeline via RabbitMQ | Accepted |
| 0005 | Hybrid real + mocked peril data sources | Accepted |
| 0006 | One-click /evaluate reconciled with human sign-off | Accepted |
| 0007 | Deterministic additive scoring model + gates | Accepted |
| 0008 | Versioned decisions (never overwrite) | Accepted |
| 0009 | Postgres system-of-record owned by Java only | Accepted |
| 0010 | Bounded retries (app-level count + TTL + DLQ), prefetch=1 | Accepted |
| 0011 | Multi-repo layout: hub + backend + ai-worker | Accepted |
