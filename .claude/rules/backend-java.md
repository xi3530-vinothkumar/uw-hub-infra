# Rule: Java / Spring Boot orchestrator

Applies to: `backend/` (Spring Boot service).

- Layering: `controller` → `service` → `repository`; domain logic never in controllers.
- Ports & adapters: `PerilSource`, and the messaging publisher/consumer, are interfaces
  with concrete adapters. Keep the scoring `RulesEngine` a pure, side-effect-free component
  (inputs → score + audit entries) so it is trivially unit-testable.
- Persistence: JPA/Hibernate. **Decisions are versioned** — insert a new row, flip
  `is_current`; never update-in-place a prior decision.
- **Idempotency:** when consuming a result, the domain write AND the `task_results` insert
  happen in ONE `@Transactional` method; ack only after commit.
- Resilience: wrap Nominatim/FEMA/USGS calls with Resilience4J circuit breakers + 5s
  timeouts + graceful fallback (geocode → keyword; peril → `unavailable` + exposure flag).
- Validation at the API boundary: `raw_text` ≤ 50 KB; photos JPEG/PNG ≤ 10 MB, ≤ 8/submission.
- Every endpoint that triggers AI work returns `202 Accepted`; the frontend polls
  `GET /submissions/{id}`.
- Scoring constants (weights, band thresholds, critical-field list, hazardous-occupancy
  list, severe-peril threshold) live in ONE config class. See `@docs/HLD.md` §12.
