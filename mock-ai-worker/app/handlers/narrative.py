"""Mock narrative handler.

Narrative is cosmetic (CLAUDE.md invariant #4): if generation fails, we fall
back to a deterministic template and never raise. Optionally, when
USE_REAL_LLM is set and an Anthropic API key is present, we call the real
Claude API (Fable 5, falling back to Opus 4.8) for a nicer narrative — but any
failure there is swallowed and the template is used instead.
"""
import logging

from .. import config

logger = logging.getLogger(__name__)

# Models per the claude-api skill: claude-fable-5 is the most capable widely
# released model; claude-opus-4-8 is the fallback. Both are exact IDs.
_PRIMARY_MODEL = "claude-fable-5"
_FALLBACK_MODEL = "claude-opus-4-8"


def _template(score, recommendation: str) -> dict:
    """Deterministic fallback narrative — never raises."""
    rec = recommendation or "REFER"
    return {
        "narrative": (
            f"This commercial property presents {rec}-level risk "
            f"(score {score}/100). Manual review recommended."
        ),
        "pricing_guidance": (
            f"Pricing guidance pending underwriter review for {rec}-level risk."
        ),
    }


def _try_real_llm(prompt: str, model: str) -> str:
    """Call the real Anthropic API for a narrative. Raises on any failure."""
    import anthropic  # local import so the dep is optional at runtime

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("No text block in LLM response")


def handle(payload: dict) -> dict:
    """Produce a narrative + pricing guidance. Never raises (invariant #4)."""
    score = payload.get("compositeScore", payload.get("score", 0))
    recommendation = payload.get("recommendation", "REFER")

    if config.USE_REAL_LLM and config.ANTHROPIC_API_KEY:
        prompt = (
            "Write a concise 2-3 sentence underwriting narrative for a "
            f"commercial property with composite risk score {score}/100 and "
            f"recommendation {recommendation}. Then add one sentence of "
            "pricing guidance."
        )
        for model in (_PRIMARY_MODEL, _FALLBACK_MODEL):
            try:
                text = _try_real_llm(prompt, model)
                return {
                    "narrative": text,
                    "pricing_guidance": (
                        f"See narrative; {recommendation}-level pricing applies."
                    ),
                }
            except Exception as exc:  # noqa: BLE001 - narrative is cosmetic
                logger.warning(
                    "Real LLM narrative failed on model %s: %s", model, exc
                )

    return _template(score, recommendation)
