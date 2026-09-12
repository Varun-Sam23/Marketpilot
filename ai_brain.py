"""MarketPilot AI reasoning layer and Chief Intelligence Agent."""

import json
import os
import re
from typing import Any

MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTIONS = """You are the MarketPilot Chief Intelligence Agent, a cautious Indian-market decision-support analyst.
You receive evidence from independent specialist agents. Your job is to adjudicate that evidence, not blindly average it.

Rules:
- Do NOT place orders or give guaranteed predictions.
- Use ONLY supplied evidence. Never invent prices, events, levels, probabilities or statistics.
- Distinguish FACT/EVIDENCE from INTERPRETATION.
- Give greater weight to fresh, directly sourced, independent evidence.
- Detect conflicts between agents and explicitly report them.
- If evidence is weak or contradictory, lower confidence and prefer a conditional thesis.
- News impact must be based only on supplied verified article information.
- Never treat missing data as negative evidence.

Return VALID JSON ONLY with exactly this structure:
{
  "market_regime":"TRENDING|RANGE|HIGH_VOLATILITY|MIXED|UNKNOWN",
  "bias":"BULLISH|NEUTRAL|BEARISH",
  "confidence":"HIGH|MEDIUM|LOW",
  "decision_score":0,
  "thesis":"...",
  "bull_case":"...",
  "base_case":"...",
  "bear_case":"...",
  "key_levels":["..."],
  "invalidation":"...",
  "drivers":["..."],
  "risks":["..."],
  "watchlist_focus":["..."],
  "conflicts":["..."],
  "evidence_quality":"STRONG|MODERATE|WEAK|INSUFFICIENT",
  "confidence_reasons":["..."],
  "news_impact":[{"headline":"...","impact":"POSITIVE|NEGATIVE|NEUTRAL|UNKNOWN","why":"..."}]
}

Decision score is a 0-100 evidence score, not a probability and not a trading instruction.
"""


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text.strip())
    except Exception:
        match = re.search(r"\{.*\}", text or "", flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def _fallback(payload: dict[str, Any], status: str, error: str | None = None) -> dict[str, Any]:
    decision = payload.get("decision") or {}
    result = {
        "enabled": False, "status": status, "provider": "Gemini", "model": MODEL,
        "market_regime": "UNKNOWN", "bias": decision.get("bias", payload.get("rule_bias", "NEUTRAL")),
        "confidence": decision.get("confidence", "LOW"), "decision_score": decision.get("score", 50),
        "thesis": "Chief AI reasoning is unavailable. Use the independently calculated evidence and verify live data.",
        "bull_case": "Unavailable for this run.", "base_case": "Use the rule-based evidence framework.",
        "bear_case": "Unavailable for this run.", "key_levels": [],
        "invalidation": "Re-evaluate when fresh market evidence confirms or rejects the current framework.",
        "drivers": payload.get("signals", []), "risks": [], "watchlist_focus": [], "conflicts": [],
        "evidence_quality": "INSUFFICIENT", "confidence_reasons": ["Chief Agent unavailable."], "news_impact": [],
    }
    if error:
        result["error"] = error[:300]
    return result


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _fallback(payload, "AI KEY NOT CONFIGURED")
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = SYSTEM_INSTRUCTIONS + "\n\nCHIEF EVIDENCE PACK:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"temperature": 0.15, "response_mime_type": "application/json"},
        )
        result = _extract_json(response.text or "")
        if not result:
            raise ValueError("Chief Agent returned non-JSON output")
        result["enabled"] = True
        result["status"] = "CHIEF INTELLIGENCE READY"
        result["provider"] = "Gemini"
        result["model"] = MODEL
        return result
    except Exception as exc:
        return _fallback(payload, "CHIEF AI ANALYSIS ERROR", str(exc))
