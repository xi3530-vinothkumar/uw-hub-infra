# Rule: Architecture boundaries

Applies to: the whole repo. These encode the invariants in `CLAUDE.md` at rule level.

- **Decision authority lives in Java only.** The rules engine (scoring, bands, gates) is
  deterministic Java code. No LLM output may influence the numeric score or the band.
- **Python AI worker is stateless and dumb.** It may only: consume a task message, call
  Ollama via the LLM adapter, parse/validate the result, publish a result message. It must
  NOT: connect to Postgres, hold submission state, make decisions, or call
  Nominatim/FEMA/USGS.
- **Enrichment stays in Java**, on a bounded executor (not the RabbitMQ result-consumer
  thread), behind a `PerilSource` port with adapters (real: Nominatim/FEMA/USGS; mocked:
  hurricane/wildfire). Callers depend on the port, never a concrete source.
- **LLM access is behind one adapter** in the Python worker. Swapping Ollama → Claude/GPT
  requires touching only that adapter and config, never business logic.
- **Java ↔ Python only via RabbitMQ.** No synchronous HTTP for AI work. See
  `@docs/HLD.md` §8 for message schemas.
- **All state changes are event-logged** and go through the orchestration state machine
  (`@docs/HLD.md` §9). Do not add side-channels that bypass status transitions.
