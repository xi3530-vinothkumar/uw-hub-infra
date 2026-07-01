# MEMORY — durable project knowledge

Domain glossary, invariants, and hard-won gotchas. Referenced from `CLAUDE.md`. Read when
you need the "why" behind a rule or an unfamiliar term.

## Domain glossary (insurance / underwriting)
- **P&C** — Property & Casualty insurance.
- **Underwriting (UW)** — evaluating a risk to decide whether to insure it and at what price.
- **COPE** — the four pillars of property risk: **C**onstruction, **O**ccupancy,
  **P**rotection, **E**xposure. The system organizes everything around COPE.
- **CAT peril** — catastrophe peril (hurricane, earthquake, major flood, wildfire).
- **Secondary peril** — smaller, more frequent events historically under-modeled but now
  costly: hail, severe convective storm (SCS), flash flood, etc.
- **TIV** — Total Insured Value (the amount at risk). Required to price; missing TIV →
  `FAILED_SCORING`.
- **ITV** — Insurance-to-Value (are we insuring the right replacement cost?). Inflation
  creates ITV gaps.
- **Loss-ratio leakage** — losses running higher than premium assumed, from mispriced risk.
- **SOV / ACORD** — common submission formats (Statement of Values; standardized ACORD forms).
- **Recommendation bands** — Accept (0–39), Refer (40–69), Decline (70–100). Composite
  score is 0–100, higher = riskier.

## System invariants (see CLAUDE.md for the canonical list)
- AI perceives + explains; the deterministic rules engine decides.
- Python AI worker: stateless, `prefetch=1`, no DB, no decisions, no peril calls.
- Every decision is `AI_PROPOSED` until human `HUMAN_APPROVED`; export gated on approval.
- Narrative failure → template fallback, still `DECIDED`, never `FAILED_AI`.
- Decisions are versioned, never overwritten. Everything is event-logged.
- Peril sources and the LLM are behind swappable adapters.

## Peril data posture (real vs mocked)
- **Real, free, no key:** Nominatim (geocoding), FEMA NFHL (flood zone), USGS Seismic
  Design Maps (earthquake).
- **Mocked (labelled):** hurricane/hail/wind (NOAA is bulk CSV only), wildfire (no free
  point-API). Same `PerilSource` interface; `source` field marks provenance.

## Gotchas / lessons
- **Ollama runs one model at a time.** Model swaps (text↔vision) cost 15–30s cold-load.
  This is *the* reason for the async RabbitMQ pipeline and `prefetch=1`. Pre-warm before demos.
- **Naive RabbitMQ nack-requeue loops forever** — it does not bound retries. Use the
  app-level `retryCount` + TTL retry queue → DLQ approach.
- **Open vision models are triage-grade**, not inspection-grade. For the best demo, use
  real photos, and set expectations accordingly.
- **`/evaluate` bypasses mid-pipeline review but NOT final sign-off** — the decision is
  `AI_PROPOSED` and needs approval. This is how the one-click path keeps UW discipline.
- **Hardware:** target machine is Apple M3 Pro / 18GB — verified feasible for
  `llama3.1:8b` + `llama3.2-vision:11b` with on-demand model loading.

## Environment facts
- Backend: Java 17 / Spring Boot. AI worker: Python 3.11 / FastAPI. Frontend: React+Vite+Tailwind.
- Models built WITH Claude Code CLI; the app RUNS on local open-source models (Ollama) — no
  paid API needed at runtime.
