# Demo Runbook — UW-Hub

End-to-end walk-through for demonstrating the AI-assisted underwriting workbench.
Covers three risk profiles: **Accept**, **Refer**, **Decline**.

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker Desktop | 4+ | Postgres + RabbitMQ |
| Java | 17 | `java -version` |
| Maven | 3.8+ | system `mvn` (no wrapper in repo) |
| Python | 3.11 | `python --version` |
| Node.js | 18+ | `node --version` |
| Ollama | latest | `ollama --version` |
| jq | any | `jq --version` — used by seed script |
| curl | any | standard on macOS/Linux |

---

## 2. First-time setup

### 2a. Pull Ollama models (one-time, ~10 GB combined)

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5vl:7b
```

Both must show `success` before starting the AI worker.  Verify:

```bash
ollama list
```

### 2b. Python virtual environment (one-time)

```bash
cd ai-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Start the stack

Open **five terminal tabs** (or panes) and run one service per tab, in this order.

### Tab 1 — Infra (Postgres + RabbitMQ)

```bash
docker compose up -d postgres rabbitmq
```

Wait ~10 s, then verify:

```bash
docker compose ps
# Both services should show "healthy"
```

RabbitMQ management UI: <http://localhost:15672>  (login: `uw` / `uwpass`)

### Tab 2 — Java orchestrator (port 8080)

```bash
cd backend
mvn spring-boot:run
```

Wait for `Started CopilotApplication` in the log, then:

```bash
curl http://localhost:8080/api/v1/health
# {"status":"UP", ...}
```

### Tab 3 — Python AI worker (port 8001)

```bash
cd ai-worker
source .venv/bin/activate
uvicorn app.main:app --port 8001 --reload
```

Wait for `pre-warm complete` in the log (model cold-loads happen here), then:

```bash
curl http://localhost:8001/health
# {"status":"ok", "ollama_reachable":true, ...}
```

### Tab 4 — React frontend (port 5173)

```bash
cd frontend
npm install   # first time only
npm run dev
```

Open <http://localhost:5173> in a browser.

### Tab 5 — Seed / demo commands

All seed and curl commands below run from this tab, from the repo root.

---

## 4. Seed the demo data

```bash
./demo/seed.sh
```

The script:
1. Checks the orchestrator is healthy.
2. Creates all three submissions via `POST /api/v1/submissions`.
3. Triggers processing — `/evaluate` (express) or `/extract` (stepwise).
4. Prints IDs and poll commands.

Note the three submission IDs printed; you will use them in the walkthrough below.

---

## 5. Three demo paths

### Path 1 — Accept (clean_office, stepwise)

**Submission:** 12-story steel-frame office in Austin TX, TIV $8.5 M, built 2016,
fully sprinklered.  All high-confidence COPE fields, no severe perils.

**Flow:** `CREATED → EXTRACTING → EXTRACTED → REVIEWING → ENRICHING → SCORING → DECIDED`

```bash
# After /extract is triggered, poll until EXTRACTED:
curl -s $API/submissions/<ID> | jq .status
# Then the pipeline continues automatically through the state machine.
```

**What to show:**

- Intake form with byte counter and two submit modes.
- Pipeline stepper advancing through each stage.
- COPE review screen: all fields green (high confidence), no amber/red highlights.
- Underwriter clicks **Confirm** to advance past the human gate.
- Risk dossier: high composite score, **Accept** band badge, full audit trail.
- Peril cards: FEMA flood (low / minimal), USGS seismic (low), hurricane (low), wildfire (low).
- Event timeline: colour-coded actors (SYSTEM / AI / USER).
- Click **Approve** → `HUMAN_APPROVED`.
- Click **Export** → JSON file downloaded.

### Path 2 — Refer (warehouse, express)

**Submission:** Suburban warehouse in Memphis TN, TIV $2.1 M, built 1999, partial
sprinklers.  Moderate risk, no severe perils.

**Flow:** `CREATED → EXTRACTING → ENRICHING → SCORING → DECIDED`  (express, COPE review skipped)

**What to show:**

- `/evaluate` mode: express badge in the stepper.
- Event log shows `REVIEW_SKIPPED`.
- Risk dossier: moderate score, **Refer** band, audit trail listing age and protection factors.
- Demonstrate COPE override: change "constructionType" from `joisted_masonry` to `masonry` →
  score updates, decision version bumps to v2.
- Approve and export.

### Path 3 — Decline (coastal_restaurant, express)

**Submission:** Wood-frame restaurant in Miami FL, TIV $3.2 M, built 1969, no sprinklers,
FEMA Zone AE, hurricane coast.

**Flow:** same express path; the **severe-peril gate** fires (hurricane + flood each ≥ 85).

**What to show:**

- Risk dossier: low composite score, **Decline** band.
- Peril cards: FEMA flood **severe** (AE zone), hurricane **severe** (FL coast) — both red.
- Audit trail entry: `GATE: severe_peril → band raised to DECLINE`.
- Export returns 409 before approval; clicking **Export** before **Approve** shows the
  error modal.
- Approve → Export demonstrates the full gated flow.

---

## 6. Key things to show (feature checklist)

- [ ] Byte counter on intake form (0 / 50 000 chars)
- [ ] Two submit modes: stepwise vs. express
- [ ] Pipeline stepper: live status polling every 3 s
- [ ] COPE review: confidence dots, amber / red field highlights, inline edit
- [ ] Risk dossier: animated score bar, band badge (green / amber / red), per-factor audit trail
- [ ] Narrative prose + pricing guidance section
- [ ] Peril cards with `source` provenance (`fema`, `usgs`, `mocked`)
- [ ] Exposure flag indicators
- [ ] Event timeline: colour-coded by actor, live updates
- [ ] COPE field override → decision version bump
- [ ] Approve button → `HUMAN_APPROVED`
- [ ] Export gated: 409 before approval, JSON download after

---

## 7. Health checks (quick reference)

```bash
# Java orchestrator
curl http://localhost:8080/api/v1/health
curl http://localhost:8080/actuator/health

# Python AI worker
curl http://localhost:8001/health

# RabbitMQ queues
curl -s -u uw:uwpass http://localhost:15672/api/queues | jq '.[].name'
```

---

## 8. Stopping the stack

```bash
# Stop background services
docker compose down

# Stop the Java and Python processes with Ctrl-C in their respective tabs.
```

To wipe state and start fresh:

```bash
docker compose down -v   # removes Postgres volume — all data lost
docker compose up -d postgres rabbitmq
```
