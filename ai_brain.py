"""MarketPilot AI reasoning layer.

Uses the Gemini API when GEMINI_API_KEY is available. Without a key it returns
an explicit fallback state instead of pretending that AI analysis was performed.
"""

import json
import os
import re
from typing import Any

MODEL = "gemini-3.8-flash"

SYSTEM_INSTRUCTIONS = """You are MarketPilot, a cautious Indian-market decision-support analyst.
You do NOT place orders and you must not present certainty or guaranteed predictions.
Use only the supplied market data and supplied news headlines. Do not invent facts,
prices, events, support levels, or statistics.

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

Keep the analysis concise, evidence-based, and suitable for a 9:30 AM pre-market dashboard.
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


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "enabled": False,
            "status": "AI KEY NOT CONFIGURED",
            "provider": "Gemini",
            "model": MODEL,
            "market_regime": "UNKNOWN",
            "bias": payload.get("rule_bias", "NEUTRAL"),
            "confidence": "LOW",
            "thesis": "AI reasoning is not enabled yet. The dashboard is showing the deterministic market framework.",
            "bull_case": "Configure GEMINI_API_KEY to generate an AI bull case.",
            "base_case": "Use the rule-based evidence shown on the dashboard.",
            "bear_case": "Configure GEMINI_API_KEY to generate an AI bear case.",
            "key_levels": [],
            "invalidation": "Re-evaluate the thesis when the live market breaks the identified levels.",
            "drivers": payload.get("signals", []),
            "risks": [],
            "watchlist_focus": [],
            "news_impact": [],
        }

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = SYSTEM_INSTRUCTIONS + "\n\nMARKET INPUT:\n" + json.dumps(
            payload, ensure_ascii=False, indent=2
        )
        response = client.interactions.create(model=MODEL, input=prompt)
        result = _extract_json(response.output_text)
        if not result:
            raise ValueError("Gemini returned non-JSON output")
        result["enabled"] = True
        result["status"] = "AI ANALYSIS READY"
        result["provider"] = "Gemini"
        result["model"] = MODEL
        return result
    except Exception as exc:
        return {
            "enabled": False,
            "status": "AI ANALYSIS ERROR",
            "provider": "Gemini",
            "model": MODEL,
            "error": str(exc)[:300],
            "market_regime": "UNKNOWN",
            "bias": payload.get("rule_bias", "NEUTRAL"),
            "confidence": "LOW",
            "thesis": "AI reasoning failed for this run. Use the rule-based evidence and verify live data.",
            "bull_case": "Unavailable for this run.",
            "base_case": "Use the rule-based framework.",
            "bear_case": "Unavailable for this run.",
            "key_levels": [],
            "invalidation": "Re-evaluate the thesis using live market confirmation.",
            "drivers": payload.get("signals", []),
            "risks": ["AI analysis unavailable"],
            "watchlist_focus": [],
            "news_impact": [],
        }
