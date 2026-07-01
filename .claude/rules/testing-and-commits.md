# Rule: Testing, commits, and workflow hygiene

Applies to: the whole repo.

- **Scoring engine:** unit tests are mandatory and must include the three worked examples
  in `@docs/HLD.md` §12 (Accept / Refer / Decline), plus each gate (severe peril, low
  confidence, missing TIV) and the no-photo exclusion.
- **Determinism test:** same inputs + same config → identical score (assert reproducibility).
- **Idempotency test:** replaying a duplicate result message must not create duplicate rows.
- **Resilience tests:** worker crash before ack → redelivery; narrative failure → template
  fallback + `DECIDED` (never `FAILED_AI`); external API failure → `unavailable` + flag.
- Commits: one logical change each; conventional-commit prefixes; reference the ticket ID
  (e.g. `feat(scoring): E1 additive model + audit entries`).
- Update `@docs/PROGRESS.md` in the same change that completes a ticket.
- Make minimal changes; do not refactor unrelated code. If two designs are viable, explain
  both and ask rather than deciding silently.
