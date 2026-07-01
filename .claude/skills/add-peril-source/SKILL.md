---
name: add-peril-source
description: "How to add a new peril/exposure data source (real API or mock) behind the enrichment adapter. Use when wiring a new hazard feed (e.g. NOAA, wildfire, a licensed CAT model) or replacing a mocked peril with a real one."
---

# Skill: Add a peril / enrichment source

1. **Implement the port, not a special case.** Add a new adapter to the `PerilSource`
   port; return `PerilExposure` objects with `peril`, `severity`, `score` (0–100),
   `rationale`, `is_secondary`, and a `source` label. Callers must not be able to tell real
   from mocked.
2. **Set the `source` field honestly** (`"FEMA NFHL"`, `"NOAA"`, `"mocked"`,
   `"unavailable"`). The UI surfaces this for provenance/auditability.
3. **Resilience is mandatory for real sources.** Wrap external calls in a Resilience4J
   circuit breaker + timeout, on the bounded enrichment executor (never the RabbitMQ
   result-consumer thread). On failure, degrade to `unavailable` + an exposure flag; do not
   fail the whole submission unless every source is down and fallback is insufficient
   (`FAILED_ENRICHMENT`).
4. **Respect provider limits** (e.g. Nominatim ≤ 1 req/sec, descriptive `User-Agent`).
5. **Severity banding** stays consistent: severe ≥ 80, elevated 60–79, moderate 35–59,
   low < 35. A severe peril triggers the severe-peril gate in scoring.
6. **Document it** in `docs/HLD.md` §14 and, if it changes the real/mock posture, an ADR.
