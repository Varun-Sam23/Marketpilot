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
    """Provide a useful rule-based interpretation when Gemini is unavailable.

    The UI should never lose the bull/base/bear framework merely because the
    optional Chief AI call failed. These cases are explicitly conditional and
    are derived only from the supplied rule-based evidence.
    """
    decision = payload.get("decision") or {}
    levels = payload.get("levels") or {}
    snapshots = payload.get("market_snapshot") or payload.get("global") or []
    bias = decision.get("bias", payload.get("rule_bias", "NEUTRAL"))
    confidence = decision.get("confidence", payload.get("rule_confidence", "LOW"))
    score = decision.get("score", 50)
    regime = decision.get("regime", "MIXED / RANGE")
    evidence = decision.get("evidence", []) or payload.get("signals", [])

    close = levels.get("NIFTY close")
    sma20 = levels.get("20D SMA")
    sma50 = levels.get("50D SMA")
    high20 = levels.get("20D high")
    low20 = levels.get("20D low")
    rsi14 = levels.get("RSI14")

    bull_trigger = decision.get("bull_trigger", "NIFTY holds above its 20D SMA and Bank Nifty confirms strength.")
    bear_trigger = decision.get("bear_trigger", "NIFTY loses its 20D SMA while volatility expands.")
    invalidation = decision.get("invalidation", "Re-evaluate when price structure and volatility move materially against the evidence pack.")

    bull_case = f"Conditional bullish case: {bull_trigger}"
    bear_case = f"Conditional bearish case: {bear_trigger}"
    base_case = f"Base case: follow the current {bias.lower()} rule-based framework ({score}/100) while waiting for fresh confirmation."

    key_levels = []
    if close is not None:
        key_levels.append(f"NIFTY close: {close}")
    if sma20 is not None:
        key_levels.append(f"20D SMA: {sma20}")
    if sma50 is not None:
        key_levels.append(f"50D SMA: {sma50}")
    if high20 is not None:
        key_levels.append(f"20D high: {high20}")
    if low20 is not None:
        key_levels.append(f"20D low: {low20}")
    if rsi14 is not None:
        key_levels.append(f"RSI14: {rsi14}")

    vix = next((x for x in snapshots if x.get("name") == "INDIA VIX"), {})
    drivers = list(evidence[:6])
    if vix.get("change_pct") is not None:
        drivers.append(f"India VIX change: {vix.get('change_pct')}%")

    result = {
        "enabled": False,
        "status": status,
        "provider": "Gemini",
        "model": MODEL,
        "market_regime": regime,
        "bias": bias,
        "confidence": confidence,
        "decision_score": score,
        "thesis": "Chief AI reasoning is unavailable; the scenario framework below is generated from the independently calculated evidence.",
        "bull_case": bull_case,
        "base_case": base_case,
        "bear_case": bear_case,
        "key_levels": key_levels,
        "invalidation": invalidation,
        "drivers": drivers,
        "risks": ["Chief AI adjudication is unavailable; verify fresh live evidence before acting."],
        "watchlist_focus": [],
        "conflicts": [],
        "evidence_quality": "MODERATE" if evidence else "INSUFFICIENT",
        "confidence_reasons": ["Scenario cases are rule-based because the Chief AI call was unavailable."],
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
