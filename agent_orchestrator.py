"""MarketPilot multi-agent orchestration layer.

Specialist agents run independently in parallel. They are deliberately small and
mostly deterministic: raw market calculations stay in the existing intelligence
engines, while the orchestration layer gives each specialist a clear role and
returns a structured evidence pack for the Chief Intelligence layer.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

from decision_engine import score_setup
from news_intelligence import enrich_news
from watchlist_intelligence import rank_watchlist


class AgentResult(dict):
    """Structured result returned by every specialist agent."""

    @classmethod
    def ok(cls, name, data, elapsed_ms):
        return cls({"agent": name, "status": "READY", "elapsed_ms": round(elapsed_ms, 1), "data": data})

    @classmethod
    def error(cls, name, error, elapsed_ms):
        return cls({"agent": name, "status": "ERROR", "elapsed_ms": round(elapsed_ms, 1), "data": {}, "error": str(error)[:300]})


def _run_agent(name, fn):
    started = perf_counter()
    try:
        return AgentResult.ok(name, fn(), (perf_counter() - started) * 1000)
    except Exception as exc:
        return AgentResult.error(name, exc, (perf_counter() - started) * 1000)


def run_specialists(*, levels, snapshots, sectors, watchlist, news_items):
    """Run MarketPilot specialist agents concurrently.

    The agents do not make independent trading decisions. They produce evidence
    that is later consumed by the Decision Engine and Chief Intelligence layer.
    """
    tasks = {
        "Market Agent": lambda: {"snapshot": snapshots, "levels": levels},
        "Technical Agent": lambda: _technical(levels),
        "News Agent": lambda: enrich_news(news_items[:24]),
        "Institutional Agent": lambda: {"status": "DELEGATED", "note": "Institutional flow engine remains the source of FII/DII evidence."},
        "Options Agent": lambda: {"status": "DELEGATED", "note": "Options intelligence engine remains the source of OI/IV/positioning evidence."},
        "Sector Agent": lambda: {"sectors": sectors},
        "Watchlist Agent": lambda: rank_watchlist(watchlist, news_items[:24]),
        "Risk Agent": lambda: _risk(levels, snapshots, sectors),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=min(8, len(tasks)), thread_name_prefix="mp-agent") as pool:
        futures = {pool.submit(_run_agent, name, fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            result = future.result()
            results[result["agent"]] = result

    return {
        "agents": results,
        "agent_count": len(tasks),
        "ready_count": sum(r["status"] == "READY" for r in results.values()),
        "error_count": sum(r["status"] == "ERROR" for r in results.values()),
        "execution": "PARALLEL",
    }


def _technical(levels):
    if not levels:
        return {"status": "INSUFFICIENT DATA"}
    close = levels.get("NIFTY close")
    sma20 = levels.get("20D SMA")
    sma50 = levels.get("50D SMA")
    rsi = levels.get("RSI14")
    return {
        "trend_vs_20d": "ABOVE" if close is not None and sma20 and close > sma20 else "BELOW" if close is not None and sma20 else "UNKNOWN",
        "trend_vs_50d": "ABOVE" if close is not None and sma50 and close > sma50 else "BELOW" if close is not None and sma50 else "UNKNOWN",
        "rsi14": rsi,
        "20d_return_pct": levels.get("20D return %"),
        "range_position_pct": levels.get("range_position_%"),
    }


def _risk(levels, snapshots, sectors):
    by = {x.get("name"): x for x in snapshots or []}
    vix = by.get("INDIA VIX", {})
    vix_change = vix.get("change_pct")
    sector_changes = [x.get("avg_change_pct") for x in sectors or [] if x.get("avg_change_pct") is not None]
    breadth = (sum(x > 0 for x in sector_changes) / len(sector_changes)) if sector_changes else None
    flags = []
    if vix_change is not None and vix_change >= 5:
        flags.append("VOLATILITY_SPIKE")
    if breadth is not None and breadth < 0.33:
        flags.append("WEAK_SECTOR_BREADTH")
    if breadth is not None and breadth > 0.67:
        flags.append("BROAD_PARTICIPATION")
    return {"vix_change_pct": vix_change, "sector_positive_share": breadth, "flags": flags}


def build_chief_input(levels, snapshots, sectors, watchlist, news, decision, specialists):
    """Create the evidence packet for the final Chief Intelligence Agent."""
    return {
        "market": {"levels": levels, "snapshots": snapshots},
        "sectors": sectors,
        "watchlist": watchlist,
        "news": news,
        "decision": decision,
        "specialists": specialists,
        "governance": {
            "rule": "Specialists provide evidence; the Chief Intelligence Agent interprets it.",
            "no_order_execution": True,
            "conflicts_must_be_reported": True,
        },
    }
