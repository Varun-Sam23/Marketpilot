"""Historical calibration and confidence diagnostics for MarketPilot."""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

HISTORY = Path("data/history.json")


def _load() -> list[dict]:
    try:
        x = json.loads(HISTORY.read_text(encoding="utf-8"))
        return x if isinstance(x, list) else []
    except Exception:
        return []


def _bucket(item: dict, key: str) -> str:
    if key == "confidence":
        return str(item.get("decision", {}).get("confidence") or item.get("rule_confidence") or "UNKNOWN").upper()
    if key == "bias":
        return str(item.get("bias") or item.get("decision", {}).get("bias") or item.get("rule_bias") or "UNKNOWN").upper()
    if key == "regime":
        return str(item.get("decision", {}).get("regime") or "UNKNOWN").upper()
    return "UNKNOWN"


def _group(rows: list[dict], key: str) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        if r.get("status") == "EVALUATED":
            groups[_bucket(r, key)].append(r)
    out = []
    for name, items in groups.items():
        correct = sum(i.get("result") == "CORRECT" for i in items)
        out.append({
            "segment": name,
            "evaluated": len(items),
            "correct": correct,
            "accuracy_pct": round(correct / len(items) * 100, 1),
            "avg_next_session_return_pct": round(sum(i.get("next_session_return_pct", 0) for i in items) / len(items), 2),
        })
    return sorted(out, key=lambda x: x["evaluated"], reverse=True)


def fetch_calibration(performance_rows: list[dict] | None = None) -> dict:
    from performance_intelligence import _evaluate
    history = _load()
    rows = performance_rows if performance_rows is not None else [_evaluate(x) for x in history]
    evaluated = [x for x in rows if x.get("status") == "EVALUATED"]
    total = len(evaluated)
    correct = sum(x.get("result") == "CORRECT" for x in evaluated)
    overall = round(correct / total * 100, 1) if total else None
    high = [x for x in evaluated if str(x.get("confidence", "")).upper() == "HIGH"]
    # Performance rows from older versions may not persist confidence; enrich from source history by date.
    source_by_date = {str(x.get("date_ist")): x for x in history}
    enriched = []
    for x in evaluated:
        src = source_by_date.get(str(x.get("date")), {})
        decision = src.get("decision", {}) or {}
        enriched.append({**x, "confidence": str(decision.get("confidence") or src.get("rule_confidence") or "UNKNOWN").upper(), "bias": str(decision.get("bias") or src.get("rule_bias") or "UNKNOWN").upper(), "regime": str(decision.get("regime") or "UNKNOWN").upper()})
    return {
        "available": bool(history), "total_theses": len(history), "evaluated": total,
        "overall_accuracy_pct": overall,
        "confidence": _group(enriched, "confidence"),
        "bias": _group(enriched, "bias"),
        "regime": _group(enriched, "regime"),
        "calibration_note": "Calibration requires a growing sample. Segment accuracy is descriptive and should not be treated as a probability until sufficient observations accumulate.",
    }
