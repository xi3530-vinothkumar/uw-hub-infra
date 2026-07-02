# Progress Tracker

Living status of the Kanban backlog (`KANBAN.md`). Check the box when a ticket is **Done**
(AC met + tests green + committed). Add a dated one-line note for anything learned or any
follow-up ticket discovered. Update this in the same change that completes a ticket.

_Last updated: 2026-07-02_ — UI/UX audit complete. Two gaps found and fixed: structured ExposureFlag (backend) + severity-coloured chips (frontend); EXTRACTED status label → "Draft Review Pending".

## Sprint 1 — Walking skeleton (async extraction end-to-end)
- [x] A1 · Docker Compose infra
- [x] A2 · Spring Boot skeleton + health
- [x] A3 · FastAPI worker skeleton + health + pre-warm
- [x] A4 · Postgres schema + migrations
- [x] B1 · Queue topology
- [x] B2 · Java publisher + result listener (idempotent)
- [x] B3 · Python consumer + retry/DLQ
- [x] C1 · Extraction (text → COPE)

## Sprint 2 — Decision core (real perils + a scored decision)
- [x] D1 · Nominatim geocoding
- [x] D2 · FEMA flood + USGS seismic
- [x] D3 · Mocked hurricane + wildfire
- [x] E1 · Deterministic scoring engine
- [x] E2 · Gates
- [x] E3 · Decision versioning + re-score
- [x] C2 · Vision analysis

## Sprint 3 — Orchestration + API
- [x] F1 · State machine + multi-photo join
- [x] F2 · /evaluate express path
- [x] F3 · Activity-based watchdog
- [x] F4 · Event logging across pipeline
- [x] G1 · Submission + stepwise endpoints
- [x] G2 · Profile override (PATCH)
- [x] G3 · Approve + export (gated)
- [x] C3 · Narrative generation

## Sprint 4 — Frontend + demo
- [x] H1 · Intake + stepper
- [x] H2 · COPE review screen
- [x] H3 · Photos, peril cards, risk dossier
- [x] H4 · Event timeline + approve/export controls
- [x] I1 · Synthetic submissions
- [x] I2 · Seed script + demo runbook

## Notes / learnings
- 2026-07-01 G1: SubmissionController (@RestController /api/v1/submissions) with all stepwise endpoints: POST / (201), POST /{id}/extract (202), POST /{id}/evaluate (202), PATCH /{id}/profile (200), POST /{id}/enrich (202), POST /{id}/score (202), GET /{id} (200), GET /{id}/events (200), POST /{id}/decision/approve (200), POST /{id}/export (200/409). SubmissionService interface expanded (create, startExtraction, evaluateExpress, startEnrichment, startScoring, getDetails, getEvents) + SubmissionServiceImpl. DTOs: CreateSubmissionRequest, SubmissionResponse, CopeProfileDTO, DecisionDTO, AuditEntryResponseDTO, EventLogDTO, ProfileOverrideRequest, ApproveRequest. SubmissionNotFoundException (→ 404). GlobalExceptionHandler (404/409/400/bean-validation). 22 new @WebMvcTest controller tests; 202 total green.
- 2026-07-01 G2+G3+E3: ProfileOverrideService: updates CopeProfile.value + overriddenByUser=true, logs FIELD_OVERRIDDEN_BY_USER; E3: if a current decision exists, flips is_current=false (decision superseded), logs DECISION_SUPERSEDED_BY_OVERRIDE, reverts submission to REVIEWED for re-score. ApprovalService: sets reviewStatus=HUMAN_APPROVED + approvedBy + approvedAt, advances submission to APPROVED, logs DECISION_APPROVED; idempotent on double-approve. ExportService: gated on HUMAN_APPROVED (throws IllegalStateException("NOT_APPROVED…") → 409 via GlobalExceptionHandler); assembles full export map (submission, copeProfile, perils, decision+auditTrail, events). SubmissionController already existed from G1 with PATCH /profile, POST /decision/approve, POST /export stubs wired to the new services. DECISION_SUPERSEDED_BY_OVERRIDE constant added to EventLogger. 16 new tests; 202 total green.
- 2026-07-01 F1+F2+F3+F4: Full orchestration state machine implemented. OrchestrationServiceImpl now handles EXTRACT/VISION/NARRATIVE results, multi-photo join barrier (DB-derived PENDING count — idempotent + crash-safe), enrichment delegation to EnrichmentService.enrich() with thenRun/exceptionally chain, runScoring (decision v+1, is_current flip, audit entries, exposure flags JSON), narrative publishing. F2 express path: evaluateExpress sets expressPath=true on Submission, handleExtractionResult auto-calls skipReview which transitions EXTRACTED→REVIEWED and kicks off vision or enrichment. F3 Watchdog: @Scheduled(fixedDelay=300_000) scans non-terminal subs with last_activity_at > 15 min stale, republishPendingTask dispatches by status. F4 EventLogger: 18 canonical event type constants (SUBMISSION_CREATED, EXTRACTION_PUBLISHED, ..., FAILED_SCORING). V2 migration adds express_path BOOLEAN column. @EnableScheduling added to CopilotApplication. AuditEntryRepository created. OrchestrationService interface expanded with startExtraction/evaluateExpress/republishPendingTask. 42 new tests; 164 total green.
- 2026-07-01 E1+E2: RulesEngine implemented as pure side-effect-free component. Additive weighted scoring across COPE completeness, occupancy, construction, age, TIV, peril exposure, photo quality, confidence. Three gates: severe-peril (any exposure score >= 85 → DECLINE), low-confidence (< 0.55 → REFER), missing-TIV (null → REFER). No-photo exclusion: vision factor zeroed. All 3 HLD §12 worked examples pass (Accept/Refer/Decline). Determinism test + gate tests green. ScoringConfig holds all weights/thresholds/constants. 130+ Java tests all green.
- 2026-07-01 D2+D3: PerilSource port (interface) created. FemaFloodAdapter: @CircuitBreaker(name="fema"), queries NFHL MapServer layer 28, maps FLD_ZONE to severe(85)/moderate(65)/low(20), fallback returns unavailable row. UsgsSeismicAdapter: @CircuitBreaker(name="usgs"), queries USGS ASCE7-22, maps Sds >=1.5/0.75/0.25 to severe(85)/moderate(60)/low(35)/minimal(10). MockHurricaneAdapter: state-token keyword match (FL/TX/LA/NC/SC/GA -> severe 80, else low 25). MockWildfireAdapter: state-token keyword match (CA/OR/WA/CO/AZ/NM/NV -> moderate 75, else low 15). EnrichmentService: geocodes, fans out to all PerilSource beans on enrichmentExecutor (3-thread pool), catches per-source exceptions as unavailable rows, persists via PerilExposureRepository, advances submission to ENRICHED. PerilExposureRepository with findBySubmissionId (JPQL) and findBySubmission_Id/findBySubmission_IdOrderByScoreDesc (Spring Data). EnrichmentConfig @Bean enrichmentExecutor. 37 new tests; 106 total green.
- 2026-07-01 D1: NominatimGeocoder uses RestClient + @CircuitBreaker(name="nominatim") + @RateLimiter(name="nominatim"). Resilience4J config (slidingWindowSize:3, failureRate:67%, waitDuration:30s, rateLimit:1req/s) added to application.yml for nominatim/fema/usgs. Fallback returns Optional.empty() so callers degrade gracefully. 8 new unit tests; 69 total green.
- 2026-07-01 I1+I2: Three synthetic submissions (demo/submissions/): accept_clean_office.json (stepwise, Accept), refer_warehouse.json (express, Refer), decline_coastal_restaurant.json (express, Decline, severe-peril gate). demo/seed.sh: bash script with preflight health check, creates + triggers each submission, prints IDs + poll commands. demo/RUNBOOK.md: full 5-tab start sequence, three demo paths, feature checklist, health checks, reset instructions. No ADR needed (operational tooling, no design decision).
- 2026-07-02 UX audit: Manual QA pass across all 6 screens vs locked design decisions. 14/18 checks passed outright. Two confirmed gaps fixed: (1) ExposureFlag promoted from List<String> to structured record {code, severity, message} in backend scoring package; frontend AuditTable now renders info=blue/warning=amber/error=red chips with legacy plain-string fallback. (2) statusLabel for EXTRACTED changed from "Extracted" to "Draft Review Pending". G2 (version in dossier header) and G3 (≥3 versions warning banner) were already implemented — pre-audit assessment was wrong. 58 backend tests green.
- 2026-07-01 A3: Added pytest test suite (tests/test_health.py + tests/test_llm_adapter.py) + requirements-test.txt; all 6 tests green. FastAPI lifespan replaces deprecated @app.on_event.
- 2026-07-01 B3: Full consumer implemented: prefetch=1, ack-after-success, retryCount < MAX -> uw.retry (TTL), retryCount >= MAX -> FAILURE result + uw.dlx. Consumer task started in FastAPI lifespan. 17 new unit tests; 23 total green.
- 2026-07-01 B2: TaskMessage/ResultMessage DTOs, Jackson2JsonMessageConverter wired in MessagingConfig, TaskPublisher (text/vision/narrative routing), ResultListener (@Transactional, idempotency guard via task_results), DlqListener (NARRATIVE->applyNarrativeFallback, EXTRACT/VISION->markFailed FAILED_AI), EventLogger (swallows all exceptions). OrchestrationService + SubmissionService declared as stub interfaces for later epics. CopilotApplicationTests updated to use @AutoConfigureTestDatabase(Replace.ANY) + MockBean interfaces. 61 tests green.
