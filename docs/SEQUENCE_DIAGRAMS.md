# Sequence Diagrams

Detailed Mermaid flows for the four key runtime paths through the underwriting pipeline.
All state names match the canonical status pipeline in `HLD.md §6` and the orchestration
state machine in `HLD.md §9`.

---

## Diagram 1 — Express `/evaluate` Path (end-to-end to DECIDED)

The underwriter submits once and the system runs straight through to an `AI_PROPOSED`
decision. COPE review is auto-skipped (logged `REVIEW_SKIPPED`). Final sign-off is still
required before export.

```mermaid
sequenceDiagram
    autonumber
    actor UW as Underwriter
    participant FE as Frontend (React)
    participant Java as Java Orchestrator
    participant DB as PostgreSQL
    participant MQ as RabbitMQ
    participant PY as Python AI Worker
    participant OL as Ollama

    UW->>FE: Submit property + POST /evaluate
    FE->>Java: POST /api/v1/submissions/{id}/evaluate
    Java-->>FE: 202 Accepted (status=PROCESSING)
    Java->>DB: persist submission, status=PROCESSING
    Java->>MQ: publish EXTRACT task (queue.task.text)
    Java->>DB: log event EXTRACT_PUBLISHED

    Note over FE,Java: Frontend polls GET /submissions/{id}

    MQ->>PY: deliver EXTRACT task (prefetch=1)
    PY->>OL: call llama3.1:8b (extraction prompt)
    OL-->>PY: structured COPE JSON
    PY->>MQ: publish result → queue.result (ack after publish)
    MQ->>Java: deliver EXTRACT result (queue.result)
    Java->>DB: BEGIN txn — persist COPE fields + task_results row (idempotency)
    Java->>DB: COMMIT; status=EXTRACTED
    Java->>DB: log REVIEW_SKIPPED (express path)
    Java->>DB: status=REVIEWED

    Note over Java: Photos present? → publish one VISION task per photo

    loop For each photo (N photos)
        Java->>MQ: publish VISION task (queue.task.vision)
        Java->>DB: log event VISION_PUBLISHED
        MQ->>PY: deliver VISION task (prefetch=1)
        PY->>OL: call qwen2.5vl:7b (vision prompt)
        OL-->>PY: findings + condition_score JSON
        PY->>MQ: publish result → queue.result (ack after publish)
        MQ->>Java: deliver VISION result
        Java->>DB: BEGIN txn — persist photo findings + task_results row
        Java->>DB: COMMIT; photo.analysis_status=DONE
        Java->>DB: log VISION_COMPLETED
    end

    Note over Java: Multi-photo join: wait until count(photos WHERE analysis_status='PENDING')=0

    Java->>Java: run enrichment on bounded executor
    Java->>Java: Nominatim geocode → lat/lng
    Java->>Java: FEMA NFHL → flood zone
    Java->>Java: USGS → seismic design category
    Java->>DB: persist peril_exposures (with source provenance)
    Java->>DB: status=ENRICHED; log per-source outcomes

    Java->>Java: run RulesEngine (deterministic, in-process)
    Note over Java: baseline 20 + Σ factors, clamped [0,100]; gates applied
    Java->>DB: INSERT decisions row v1 (review_status=AI_PROPOSED, is_current=true)
    Java->>DB: INSERT audit_entries (one row per factor)
    Java->>DB: status=SCORED; log SCORING_COMPLETED
    Java->>MQ: publish NARRATIVE task (queue.task.text)
    Java->>DB: log NARRATIVE_PUBLISHED

    MQ->>PY: deliver NARRATIVE task (prefetch=1)
    PY->>OL: call llama3.1:8b (narrative prompt)
    OL-->>PY: narrative text JSON
    PY->>MQ: publish result → queue.result (ack after publish)
    MQ->>Java: deliver NARRATIVE result
    Java->>DB: BEGIN txn — update decisions.narrative + task_results row
    Java->>DB: COMMIT; narrative_source="ai"; status=DECIDED
    Java->>DB: log NARRATIVE_COMPLETED

    FE->>Java: GET /submissions/{id} (poll)
    Java-->>FE: status=DECIDED + dossier
    FE-->>UW: Show risk dossier (score, band, narrative, audit trail, exposure flags)

    Note over UW,FE: Decision is AI_PROPOSED — export blocked until approved
    UW->>FE: POST /decision/approve
    FE->>Java: POST /api/v1/submissions/{id}/decision/approve
    Java->>DB: decisions.review_status=HUMAN_APPROVED; status=APPROVED
    Java->>DB: log DECISION_APPROVED (actor=underwriter)
    Java-->>FE: 200 OK
    FE-->>UW: Export button unlocked
```

---

## Diagram 2 — Stepwise Path (Pauses for COPE Review)

Identical to the express path up to `EXTRACTED`, but then the system pauses. The
underwriter reviews the extracted COPE fields (with per-field confidence and source
snippets), optionally edits them via `PATCH /profile`, and explicitly advances to
`REVIEWED` before vision/enrich/score proceed.

```mermaid
sequenceDiagram
    autonumber
    actor UW as Underwriter
    participant FE as Frontend (React)
    participant Java as Java Orchestrator
    participant DB as PostgreSQL
    participant MQ as RabbitMQ
    participant PY as Python AI Worker
    participant OL as Ollama

    UW->>FE: Submit property + POST /extract (stepwise)
    FE->>Java: POST /api/v1/submissions/{id}/extract
    Java-->>FE: 202 Accepted (status=PROCESSING)
    Java->>DB: status=PROCESSING
    Java->>MQ: publish EXTRACT task (queue.task.text)
    Java->>DB: log event EXTRACT_PUBLISHED

    MQ->>PY: deliver EXTRACT task (prefetch=1)
    PY->>OL: call llama3.1:8b (extraction prompt)
    OL-->>PY: structured COPE JSON
    PY->>MQ: publish result → queue.result (ack after publish)
    MQ->>Java: deliver EXTRACT result
    Java->>DB: BEGIN txn — persist COPE fields + task_results row
    Java->>DB: COMMIT; status=EXTRACTED
    Java->>DB: log EXTRACTION_COMPLETED

    Note over FE,Java: Frontend polls → status=EXTRACTED

    FE->>Java: GET /submissions/{id}
    Java-->>FE: status=EXTRACTED + COPE fields (confidence + source snippets)
    FE-->>UW: Show COPE review screen (per-field confidence, source snippets, edit controls)

    Note over UW,FE: Underwriter inspects fields; may edit one or more

    UW->>FE: Edit fields + submit overrides
    FE->>Java: PATCH /api/v1/submissions/{id}/profile (overridden values)
    Java->>DB: persist overrides; overridden_by_user=true
    Java->>DB: status=REVIEWED; log FIELD_OVERRIDDEN_BY_USER (per field changed)
    Java-->>FE: 200 OK

    Note over Java: REVIEWED → check for photos → publish VISION tasks

    loop For each photo (N photos)
        Java->>MQ: publish VISION task (queue.task.vision)
        Java->>DB: log VISION_PUBLISHED
        MQ->>PY: deliver VISION task (prefetch=1)
        PY->>OL: call qwen2.5vl:7b (vision prompt)
        OL-->>PY: findings + condition_score JSON
        PY->>MQ: publish result → queue.result (ack after publish)
        MQ->>Java: deliver VISION result
        Java->>DB: BEGIN txn — persist photo findings + task_results row
        Java->>DB: COMMIT; photo.analysis_status=DONE
        Java->>DB: log VISION_COMPLETED
    end

    Note over Java: Multi-photo join: all photos DONE → proceed to enrichment

    Java->>Java: run enrichment on bounded executor (Nominatim / FEMA / USGS)
    Java->>DB: persist peril_exposures; status=ENRICHED

    Java->>Java: run RulesEngine (deterministic)
    Java->>DB: INSERT decisions v1 (AI_PROPOSED); INSERT audit_entries
    Java->>DB: status=SCORED; log SCORING_COMPLETED
    Java->>MQ: publish NARRATIVE task (queue.task.text)

    MQ->>PY: deliver NARRATIVE task (prefetch=1)
    PY->>OL: call llama3.1:8b (narrative prompt)
    OL-->>PY: narrative text JSON
    PY->>MQ: publish result → queue.result (ack after publish)
    MQ->>Java: deliver NARRATIVE result
    Java->>DB: BEGIN txn — update narrative + task_results row
    Java->>DB: COMMIT; status=DECIDED; log NARRATIVE_COMPLETED

    FE->>Java: GET /submissions/{id} (poll)
    Java-->>FE: status=DECIDED + full dossier
    FE-->>UW: Show risk dossier
    UW->>FE: POST /decision/approve
    FE->>Java: POST /api/v1/submissions/{id}/decision/approve
    Java->>DB: review_status=HUMAN_APPROVED; status=APPROVED; log DECISION_APPROVED
    Java-->>FE: 200 OK
```

---

## Diagram 3 — Failure Recovery (FAILED_AI → Manual Entry)

The Python worker fails to extract or analyse a photo. It exhausts all three retry
attempts (published to the TTL retry queue each time with `retryCount+1`) and the task
lands on the DLQ. Java's `DlqListener` consumes it, sets the submission to `FAILED_AI`,
and the underwriter is offered a retry or manual COPE entry path.

```mermaid
sequenceDiagram
    autonumber
    actor UW as Underwriter
    participant FE as Frontend (React)
    participant Java as Java Orchestrator
    participant DB as PostgreSQL
    participant MQ as RabbitMQ
    participant PY as Python AI Worker
    participant OL as Ollama

    UW->>FE: Submit property + POST /extract
    FE->>Java: POST /api/v1/submissions/{id}/extract
    Java-->>FE: 202 Accepted (status=PROCESSING)
    Java->>MQ: publish EXTRACT task (retryCount=0)
    Java->>DB: log EXTRACT_PUBLISHED

    Note over MQ,PY: Attempt 1 (retryCount=0)

    MQ->>PY: deliver EXTRACT task (prefetch=1)
    PY->>OL: call llama3.1:8b
    OL-->>PY: error / timeout / bad JSON
    Note over PY: retryCount(0) < 3 → re-publish with retryCount=1 to queue.retry.text (TTL)
    PY->>MQ: publish to queue.retry.text (retryCount=1, with TTL delay)
    PY->>MQ: ack original task
    Java->>DB: log TASK_RETRY (retryCount=1)

    Note over MQ: TTL expires → dead-letters back to queue.task.text

    Note over MQ,PY: Attempt 2 (retryCount=1)

    MQ->>PY: redeliver from queue.task.text (retryCount=1)
    PY->>OL: call llama3.1:8b
    OL-->>PY: error / timeout / bad JSON
    Note over PY: retryCount(1) < 3 → re-publish retryCount=2 to queue.retry.text
    PY->>MQ: publish to queue.retry.text (retryCount=2, TTL)
    PY->>MQ: ack
    Java->>DB: log TASK_RETRY (retryCount=2)

    Note over MQ: TTL expires → dead-letters back to queue.task.text

    Note over MQ,PY: Attempt 3 (retryCount=2)

    MQ->>PY: redeliver from queue.task.text (retryCount=2)
    PY->>OL: call llama3.1:8b
    OL-->>PY: error / timeout / bad JSON
    Note over PY: retryCount(2) < 3 → re-publish retryCount=3 to queue.retry.text
    PY->>MQ: publish to queue.retry.text (retryCount=3, TTL)
    PY->>MQ: ack
    Java->>DB: log TASK_RETRY (retryCount=3)

    Note over MQ: TTL expires → dead-letters back to queue.task.text

    Note over MQ,PY: Attempt 4 (retryCount=3 — exhausted)

    MQ->>PY: redeliver from queue.task.text (retryCount=3)
    PY->>OL: call llama3.1:8b
    OL-->>PY: error / timeout / bad JSON
    Note over PY: retryCount(3) >= 3 → publish to DLQ; ack original
    PY->>MQ: publish to queue.dlq.text (taskType=EXTRACT)
    PY->>MQ: ack task
    Java->>DB: log TASK_EXHAUSTED_TO_DLQ

    Note over Java: DlqListener consumes queue.dlq.text

    MQ->>Java: DlqListener receives EXTRACT task from queue.dlq.text
    Note over Java: taskType=EXTRACT/VISION → FAILED_AI (not narrative → no fallback here)
    Java->>DB: status=FAILED_AI; failure_reason="extraction failed after 3 retries"
    Java->>DB: log EXTRACT_FAILED_AI

    FE->>Java: GET /submissions/{id} (poll)
    Java-->>FE: status=FAILED_AI + failure_reason
    FE-->>UW: Show error banner with "Retry AI Extraction" and "Enter COPE Manually" buttons

    alt Underwriter clicks Retry
        UW->>FE: click "Retry AI Extraction"
        FE->>Java: POST /api/v1/submissions/{id}/extract
        Java->>DB: status=PROCESSING; clear failure_reason
        Java->>MQ: publish fresh EXTRACT task (retryCount=0)
        Java-->>FE: 202 Accepted
        Note over FE,Java: Normal extraction flow resumes
    else Underwriter enters COPE manually
        UW->>FE: fill COPE fields manually + submit
        FE->>Java: PATCH /api/v1/submissions/{id}/profile
        Java->>DB: persist manual COPE; overridden_by_user=true; status=REVIEWED
        Java->>DB: log MANUAL_COPE_ENTRY
        Java-->>FE: 200 OK
        Note over Java: Continues from REVIEWED (vision → enrich → score)
    end
```

---

## Diagram 4 — Override + Re-score (Decision v2)

After a decision exists (either `AI_PROPOSED` or `HUMAN_APPROVED`), the underwriter
discovers an incorrect COPE field and patches it. The orchestrator supersedes the current
decision, resets status to `REVIEWED`, and the underwriter triggers a fresh scoring run
that produces decision v2.

```mermaid
sequenceDiagram
    autonumber
    actor UW as Underwriter
    participant FE as Frontend (React)
    participant Java as Java Orchestrator
    participant DB as PostgreSQL
    participant MQ as RabbitMQ
    participant PY as Python AI Worker
    participant OL as Ollama

    Note over UW,FE: Submission is in DECIDED or APPROVED state with decision v1

    FE-->>UW: Show risk dossier (score, band, per-factor audit trail)
    UW->>FE: Spot incorrect field (e.g. wrong construction_type)

    UW->>FE: Edit field + submit override
    FE->>Java: PATCH /api/v1/submissions/{id}/profile {field: construction_type, value: "Frame"}
    Java->>DB: BEGIN txn
    Java->>DB: UPDATE cope_profiles: value=Frame, overridden_by_user=true
    Note over Java: A current decision exists → must supersede it
    Java->>DB: UPDATE decisions SET is_current=false WHERE submission_id=? AND is_current=true  (v1 superseded)
    Java->>DB: status=REVIEWED
    Java->>DB: log FIELD_OVERRIDDEN_BY_USER (field=construction_type, old_value, new_value, actor=underwriter)
    Java->>DB: COMMIT
    Java-->>FE: 200 OK

    FE-->>UW: Show "Re-score required" prompt (dossier shows stale v1 marked superseded)

    UW->>FE: click "Re-score" (or POST /score)
    FE->>Java: POST /api/v1/submissions/{id}/score
    Java-->>FE: 202 Accepted (status back to SCORED in progress)

    Note over Java: Re-run RulesEngine with updated COPE profile (Frame +15 vs prior class)
    Java->>Java: run RulesEngine (deterministic, in-process)
    Java->>DB: INSERT decisions row v2 (is_current=true, review_status=AI_PROPOSED)
    Java->>DB: INSERT audit_entries for v2 (one row per factor)
    Java->>DB: status=SCORED; log SCORING_COMPLETED (version=2)
    Java->>MQ: publish NARRATIVE task (queue.task.text)
    Java->>DB: log NARRATIVE_PUBLISHED

    MQ->>PY: deliver NARRATIVE task (prefetch=1)
    PY->>OL: call llama3.1:8b (narrative prompt with updated score + factors)
    OL-->>PY: updated narrative text JSON
    PY->>MQ: publish result → queue.result (ack after publish)
    MQ->>Java: deliver NARRATIVE result
    Java->>DB: BEGIN txn — update decisions v2 narrative + task_results row
    Java->>DB: COMMIT; narrative_source="ai"; status=DECIDED
    Java->>DB: log NARRATIVE_COMPLETED

    FE->>Java: GET /submissions/{id} (poll)
    Java-->>FE: status=DECIDED + decision v2 (AI_PROPOSED) + updated dossier
    FE-->>UW: Show updated risk dossier (v2 score/band, v1 retained in audit history)

    Note over UW,FE: v1 row still in DB (is_current=false); full audit trail preserved

    UW->>FE: Review updated dossier + approve
    FE->>Java: POST /api/v1/submissions/{id}/decision/approve
    Java->>DB: decisions v2: review_status=HUMAN_APPROVED; status=APPROVED
    Java->>DB: log DECISION_APPROVED (version=2, actor=underwriter)
    Java-->>FE: 200 OK
    FE-->>UW: Export button unlocked (acts on current decision v2)
```
