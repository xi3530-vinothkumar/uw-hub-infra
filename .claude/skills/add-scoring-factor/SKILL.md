---
name: add-scoring-factor
description: "How to add or change a factor, weight, band threshold, or gate in the deterministic scoring engine safely. Use when modifying underwriting risk logic, tuning weights, or adding a new COPE-derived scoring input."
---

# Skill: Add or change a scoring factor

The scoring engine is the system's most safety-critical, defensibility-critical code.
Treat every change here with extra care.

1. **Change constants, not scattered logic.** All weights, band thresholds, the critical-
   field list, the hazardous-occupancy list, and the severe-peril threshold live in the one
   scoring config class. Add/modify there.
2. **Emit an audit entry.** Every factor that contributes must produce exactly one
   `audit_entries` row (`factor`, `impact`, `explanation`). A new factor with no audit
   entry is a bug — it breaks explainability.
3. **Handle nulls conservatively.** COPE fields may be missing. Define the "unknown"
   behavior explicitly (see §12 defaults). Never assume a non-null value.
4. **Never let AI influence the number.** Factor inputs come only from COPE fields,
   enrichment peril scores, and the vision condition score — never from LLM prose.
5. **Update tests.** Adjust the three worked examples in `docs/HLD.md` §12 if their
   expected scores change, and add a targeted test for the new factor/gate. Keep the
   determinism test green.
6. **Gates raise the band upward only** — never downward. Preserve this when touching gates.
7. **Document it.** Update `docs/HLD.md` §12 and, if it's a real policy decision, an ADR.
