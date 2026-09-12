"""Autonomous agent governance for MarketPilot.

This layer gives each specialist a mission, evidence contract, confidence score,
source awareness and a self-check. It does not invent missing data. Agents may
mark evidence insufficient and the orchestrator can escalate conflicts.
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
        verified = sum(1 for row in rows if row.get("claim_status") in {"SUPPORTED", "DISPUTED"})
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


def challenge_agents(results: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """Run deterministic cross-agent challenges before the Chief sees evidence."""
    conflicts: list[dict[str, str]] = []
    technical = results.get("Technical Agent", {}).get("data", {})
    options = results.get("Options Agent", {}).get("data", {})
    risk = results.get("Risk Agent", {}).get("data", {})
    if technical.get("trend_vs_20d") == "ABOVE" and options.get("oi_bias") == "BEARISH":
        conflicts.append({"agents": "Technical Agent ↔ Options Agent", "issue": "Price trend is above 20D SMA while options positioning is bearish.", "resolution": "Chief must treat this as a live conflict and reduce confidence unless additional evidence resolves it."})
    if technical.get("trend_vs_20d") == "BELOW" and options.get("oi_bias") == "BULLISH":
        conflicts.append({"agents": "Technical Agent ↔ Options Agent", "issue": "Price trend is below 20D SMA while options positioning is bullish.", "resolution": "Chief must treat this as a live conflict and reduce confidence unless additional evidence resolves it."})
    if "VOLATILITY_SPIKE" in (risk.get("flags") or []):
        conflicts.append({"agents": "Risk Agent", "issue": "Volatility spike detected.", "resolution": "Chief should require stronger confirmation before assigning high confidence."})
    return conflicts
