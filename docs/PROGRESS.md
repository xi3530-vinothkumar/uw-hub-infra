# Progress Tracker

Living status of the Kanban backlog (`KANBAN.md`). Check the box when a ticket is **Done**
(AC met + tests green + committed). Add a dated one-line note for anything learned or any
follow-up ticket discovered. Update this in the same change that completes a ticket.

_Last updated: 2026-07-01_ — D2+D3 done: PerilSource port, FEMA/USGS adapters, mock hurricane/wildfire, EnrichmentService + executor. 106 Java tests all green.

## Sprint 1 — Walking skeleton (async extraction end-to-end)
- [x] A1 · Docker Compose infra
- [x] A2 · Spring Boot skeleton + health
- [x] A3 · FastAPI worker skeleton + health + pre-warm
- [x] A4 · Postgres schema + migrations
- [x] B1 · Queue topology
- [x] B2 · Java publisher + result listener (idempotent)
- [x] B3 · Python consumer + retry/DLQ
- [~] C1 · Extraction (text → COPE)

## Sprint 2 — Decision core (real perils + a scored decision)
- [x] D1 · Nominatim geocoding
- [x] D2 · FEMA flood + USGS seismic
- [x] D3 · Mocked hurricane + wildfire
- [~] E1 · Deterministic scoring engine
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
- 2026-07-01 D2+D3: PerilSource port (interface) created. FemaFloodAdapter: @CircuitBreaker(name="fema"), queries NFHL MapServer layer 28, maps FLD_ZONE to severe(85)/moderate(65)/low(20), fallback returns unavailable row. UsgsSeismicAdapter: @CircuitBreaker(name="usgs"), queries USGS ASCE7-22, maps Sds >=1.5/0.75/0.25 to severe(85)/moderate(60)/low(35)/minimal(10). MockHurricaneAdapter: state-token keyword match (FL/TX/LA/NC/SC/GA -> severe 80, else low 25). MockWildfireAdapter: state-token keyword match (CA/OR/WA/CO/AZ/NM/NV -> moderate 75, else low 15). EnrichmentService: geocodes, fans out to all PerilSource beans on enrichmentExecutor (3-thread pool), catches per-source exceptions as unavailable rows, persists via PerilExposureRepository, advances submission to ENRICHED. PerilExposureRepository with findBySubmissionId (JPQL) and findBySubmission_Id/findBySubmission_IdOrderByScoreDesc (Spring Data). EnrichmentConfig @Bean enrichmentExecutor. 37 new tests; 106 total green.
- 2026-07-01 D1: NominatimGeocoder uses RestClient + @CircuitBreaker(name="nominatim") + @RateLimiter(name="nominatim"). Resilience4J config (slidingWindowSize:3, failureRate:67%, waitDuration:30s, rateLimit:1req/s) added to application.yml for nominatim/fema/usgs. Fallback returns Optional.empty() so callers degrade gracefully. 8 new unit tests; 69 total green.
- 2026-07-01 A3: Added pytest test suite (tests/test_health.py + tests/test_llm_adapter.py) + requirements-test.txt; all 6 tests green. FastAPI lifespan replaces deprecated @app.on_event.
- 2026-07-01 B3: Full consumer implemented: prefetch=1, ack-after-success, retryCount < MAX -> uw.retry (TTL), retryCount >= MAX -> FAILURE result + uw.dlx. Consumer task started in FastAPI lifespan. 17 new unit tests; 23 total green.
- 2026-07-01 B2: TaskMessage/ResultMessage DTOs, Jackson2JsonMessageConverter wired in MessagingConfig, TaskPublisher (text/vision/narrative routing), ResultListener (@Transactional, idempotency guard via task_results), DlqListener (NARRATIVE->applyNarrativeFallback, EXTRACT/VISION->markFailed FAILED_AI), EventLogger (swallows all exceptions). OrchestrationService + SubmissionService declared as stub interfaces for later epics. CopilotApplicationTests updated to use @AutoConfigureTestDatabase(Replace.ANY) + MockBean interfaces. 61 tests green.
