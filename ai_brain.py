"""MarketPilot AI reasoning layer.

Uses Google's stable Gemini 2.5 Flash model when GEMINI_API_KEY is available.
Without a key or when the API fails, returns an explicit fallback state.
"""

import json
import os
import re
from typing import Any

MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTIONS = """You are MarketPilot, a cautious Indian-market decision-support analyst.
You do NOT place orders and you must not present certainty or guaranteed predictions.
Use only the supplied market data and supplied news. Do not invent facts, prices,
events, support levels, targets, probabilities, or statistics.

Your task is to produce a concise pre-market intelligence brief for an Indian market
participant. Separate evidence from interpretation. Prefer a conditional thesis over
a directional call when evidence conflicts.

Return VALID JSON ONLY with this exact top-level structure:
{
  "market_regime": "TRENDING|RANGE|HIGH_VOLATILITY|MIXED|UNKNOWN",
  "bias": "BULLISH|NEUTRAL|BEARISH",
  "confidence": "HIGH|MEDIUM|LOW",
  "thesis": "...",
  "bull_case": "...",
  "base_case": "...",
  "bear_case": "...",
  "key_levels": ["..."],
  "invalidation": "...",
  "drivers": ["..."],
  "risks": ["..."],
  "watchlist_focus": ["..."],
  "news_impact": [
    {"headline": "...", "impact": "POSITIVE|NEGATIVE|NEUTRAL|UNKNOWN", "why": "..."}
  ]
}

Keep it concise enough to fit on a 9:30 AM dashboard. Do not give a direct buy/sell
instruction. Use levels supplied in the input rather than inventing precise ones.
"""


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def _fallback(payload: dict[str, Any], status: str, error: str | None = None) -> dict[str, Any]:
    result = {
        "enabled": False,
        "status": status,
        "provider": "Gemini",
        "model": MODEL,
        "market_regime": "UNKNOWN",
        "bias": payload.get("rule_bias", "NEUTRAL"),
        "confidence": "LOW",
        "thesis": "AI reasoning is unavailable for this run. Use the rule-based evidence and verify live data.",
        "bull_case": "Unavailable for this run.",
        "base_case": payload.get("summary", "Use the rule-based framework."),
        "bear_case": "Unavailable for this run.",
        "key_levels": [],
        "invalidation": "Re-evaluate the thesis when live price action confirms or rejects the important levels.",
        "drivers": payload.get("signals", []),
        "risks": [],
        "watchlist_focus": [],
        "news_impact": [],
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
        prompt = SYSTEM_INSTRUCTIONS + "\n\nMARKET INPUT:\n" + json.dumps(
            payload, ensure_ascii=False, indent=2
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )

        result = _extract_json(response.text or "")
        if not result:
            raise ValueError("Gemini returned non-JSON output")

        result["enabled"] = True
        result["status"] = "AI ANALYSIS READY"
        result["provider"] = "Gemini"
        result["model"] = MODEL
        return result

    except Exception as exc:
        return _fallback(payload, "AI ANALYSIS ERROR", str(exc))
