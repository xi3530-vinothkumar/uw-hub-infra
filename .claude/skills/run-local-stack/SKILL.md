---
name: run-local-stack
description: "How to run the full local stack (Postgres, RabbitMQ, Ollama, Java orchestrator, Python AI worker, React frontend) for development and demos. Use when setting up the environment, starting/stopping services, pulling models, or preparing for a live demo."
---

# Skill: Run the local stack

Order matters — infra and models must be up before the services.

1. **Infra (Docker):** `docker compose up -d postgres rabbitmq` (and `minio` if enabled).
   RabbitMQ management UI at http://localhost:15672.
2. **Ollama + models (once):**
   `ollama pull llama3.1:8b` and `ollama pull llama3.2-vision:11b`
   (fallback: `ollama pull llava:7b`). Ensure `ollama serve` is running (http://localhost:11434).
3. **Python AI worker:** create venv, `pip install -r requirements.txt`, then start it.
   It connects to RabbitMQ and pre-warms both models. Check `GET /health` reports Ollama up.
4. **Java orchestrator:** `./mvnw spring-boot:run` (or run the jar). Verify
   `GET /api/v1/health` returns Postgres + RabbitMQ + worker all healthy.
5. **Frontend:** `npm install && npm run dev` (Vite dev server, default http://localhost:5173).

**Demo prep:** run one throwaway `/evaluate` end-to-end a few minutes before presenting so
both Ollama models are warm (avoids a cold-load spinner on the first live run). Seed demo
data via the seed script (ticket I2) so low/med/high-risk submissions are ready.

**Gotcha:** an M3 Pro / 18GB runs one model at a time; the first call after a model swap is
slow while the model loads, then fast. This is expected — do not "fix" it by loading both
models concurrently (breaks the prefetch=1 invariant).
