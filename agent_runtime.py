"""Autonomous agent governance and debate for MarketPilot.

This layer gives each specialist a mission, evidence contract, confidence score,
source awareness, self-checks and bounded cross-agent debate. It never invents
missing facts and never executes trades.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Mission:
    name: str
    objective: str
    required_fields: tuple[str, ...]
    fallback_allowed: bool = True


MISSIONS = {
    "Market Agent": Mission("Market Agent", "Establish the current index and macro snapshot.", ("snapshot",)),
    "Technical Agent": Mission("Technical Agent", "Assess trend, momentum and range structure.", ("trend_vs_20d", "trend_vs_50d")),
    "News Agent": Mission("News Agent", "Verify and summarize market-moving news from publisher evidence.", ()),
    "Institutional Agent": Mission("Institutional Agent", "Establish FII/DII positioning from an attributable source chain.", ()),
    "Options Agent": Mission("Options Agent", "Assess NIFTY options positioning from attributable chain data.", ()),
    "Intraday Agent": Mission("Intraday Agent", "Assess live market structure using VWAP, opening range and momentum.", ()),
    "Sector Agent": Mission("Sector Agent", "Assess sector participation and rotation.", ("sectors",)),
    "Watchlist Agent": Mission("Watchlist Agent", "Rank watched stocks using price and catalyst evidence.", ()),
    "Risk Agent": Mission("Risk Agent", "Identify volatility, breadth and evidence-quality risks.", ("flags",)),
}


def _available(value: Any) -> bool:
    if value is None or value == "" or value == [] or value == {}:
        return False
    if isinstance(value, str) and value.upper() in {"UNKNOWN", "N/A", "UNAVAILABLE", "INSUFFICIENT DATA"}:
        return False
    return True


def assess(name: str, data: Any, error: str | None = None) -> dict[str, Any]:
    """Self-check one agent result without fabricating facts."""
    mission = MISSIONS[name]
    if error:
        return {"confidence": "LOW", "evidence_state": "ERROR", "missing": list(mission.required_fields), "needs_retry": mission.fallback_allowed}
    missing = [field for field in mission.required_fields if not _available(data.get(field) if isinstance(data, dict) else None)]
    if missing:
        return {"confidence": "LOW", "evidence_state": "INSUFFICIENT", "missing": missing, "needs_retry": mission.fallback_allowed}
    if name == "News Agent":
        rows = data if isinstance(data, list) else []
        verified = sum(1 for row in rows if row.get("research_state") in {"CORROBORATED", "CROSS_CHECKED"})
        return {"confidence": "HIGH" if verified >= 3 else "MEDIUM" if verified else "LOW", "evidence_state": "VERIFIED" if verified else "INSUFFICIENT", "verified_items": verified, "missing": [], "needs_retry": not bool(verified)}
    return {"confidence": "MEDIUM", "evidence_state": "READY", "missing": [], "needs_retry": False}


def attach_governance(name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Attach mission, confidence and self-check metadata to an AgentResult."""
    result = dict(result)
    data = result.get("data", {})
    result["mission"] = MISSIONS[name].objective
    result["self_check"] = assess(name, data, result.get("error") if result.get("status") == "ERROR" else None)
    result["autonomy"] = {
        "source_selection": "SPECIALIZED_ENGINE",
        "self_evaluation": True,
        "retry_policy": "FALLBACK_WHEN_AVAILABLE",
        "no_fabrication": True,
    }
    return result


def _challenge(challenger: str, target: str, claim: str, trigger: str, severity: str = "MEDIUM") -> dict[str, str]:
    return {
        "challenger": challenger,
        "target": target,
        "claim": claim,
        "trigger": trigger,
        "severity": severity,
        "response_required": "TARGET_MUST_CONFIRM_OR_REVISE",
        "resolution": "PENDING_CHIEF",
    }


def debate_agents(results: dict[str, dict[str, Any]], max_debates: int = 5) -> list[dict[str, str]]:
    """Run a bounded, evidence-triggered debate between specialist agents.

    This is intentionally deterministic: a debate is created only when two
    available specialist outputs create a concrete tension. The Chief gets the
    unresolved challenge and must adjudicate it rather than averaging signals.
    """
    debates: list[dict[str, str]] = []
    technical = results.get("Technical Agent", {}).get("data", {})
    options = results.get("Options Agent", {}).get("data", {})
    intraday = results.get("Intraday Agent", {}).get("data", {})
    risk = results.get("Risk Agent", {}).get("data", {})
    sectors = results.get("Sector Agent", {}).get("data", {}).get("sectors", [])
    institutional = results.get("Institutional Agent", {}).get("data", {})

    if technical.get("trend_vs_20d") == "ABOVE" and options.get("oi_bias") == "BEARISH":
        debates.append(_challenge("Options Agent", "Technical Agent", "Options positioning challenges the bullish implication of price trend.", "20D trend is ABOVE while OI bias is BEARISH.", "HIGH"))
    elif technical.get("trend_vs_20d") == "BELOW" and options.get("oi_bias") == "BULLISH":
        debates.append(_challenge("Technical Agent", "Options Agent", "Price trend challenges the bullish implication of options positioning.", "20D trend is BELOW while OI bias is BULLISH.", "HIGH"))

    headline = str(intraday.get("headline", ""))
    if headline and risk.get("flags") and any(x in headline.upper() for x in ("BULL", "BREAKOUT", "STRENGTH")) and "VOLATILITY_SPIKE" in risk.get("flags", []):
        debates.append(_challenge("Risk Agent", "Intraday Agent", "Volatility conditions challenge a high-confidence intraday strength interpretation.", "Intraday strength coincides with a volatility spike.", "HIGH"))

    positive = [x for x in sectors if (x.get("avg_change_pct") or 0) > 0]
    negative = [x for x in sectors if (x.get("avg_change_pct") or 0) < 0]
    if positive and negative and len(positive) <= len(negative):
        debates.append(_challenge("Risk Agent", "Sector Agent", "Uneven sector participation challenges a broad-market strength conclusion.", "Positive sectors do not represent a broad majority.", "MEDIUM"))

    if institutional and institutional.get("net_fii") is not None and institutional.get("net_fii") < 0:
        debates.append(_challenge("Institutional Agent", "Market Agent", "Negative FII flow challenges an unqualified bullish market snapshot.", "FII net flow is negative in the available institutional data.", "MEDIUM"))

    news = results.get("News Agent", {}).get("data", [])
    verified = [x for x in news if x.get("research_state") in {"CORROBORATED", "CROSS_CHECKED"}]
    if len(verified) == 0 and news:
        debates.append(_challenge("Risk Agent", "News Agent", "News conclusions lack sufficient independent corroboration.", "No news item reached CROSS_CHECKED or CORROBORATED status.", "MEDIUM"))

    return debates[:max_debates]


def challenge_agents(results: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """Backward-compatible conflict view derived from the debate layer."""
    debates = debate_agents(results)
    return [
        {"agents": f"{d['challenger']} ↔ {d['target']}", "issue": d["claim"], "resolution": "Chief must adjudicate: " + d["trigger"]}
        for d in debates
    ]
