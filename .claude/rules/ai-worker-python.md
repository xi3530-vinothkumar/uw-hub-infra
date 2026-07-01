# Rule: Python / FastAPI AI worker

Applies to: `ai-worker/` (FastAPI + RabbitMQ consumer).

- **Stateless.** No database, no submission state, no decisions, no peril/geocoding calls.
- Single consumer, **`prefetch_count = 1`** (Ollama serves one model at a time). Never add
  concurrency to the consumer.
- **Ack-after-success:** ack a task only after the result message is published.
- Retry topology (see `@docs/HLD.md` §8): on failure, if `retryCount < 3` re-publish with
  `retryCount+1` to the TTL retry queue; if `≥ 3` publish to the DLQ; then ack. Never rely
  on naive nack-requeue (it loops forever).
- **JSON discipline:** models must return a single JSON object. On parse failure, retry
  once in-worker with a stricter "JSON only" prompt before entering the retry topology.
- All model calls go through the single `LLMAdapter` (Ollama today). Model names come from
  config, not literals scattered in code.
- Pre-warm both models on startup (throwaway prompt each) to avoid cold-load latency.
- Expose `GET /health` reporting Ollama reachability + model availability.
