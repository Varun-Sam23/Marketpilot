"""MarketPilot multi-agent orchestration layer.

Specialist agents run independently in parallel. Raw calculations stay in the
existing intelligence engines; agents package evidence for the final reasoning
layer. The design is intentionally hybrid: deterministic calculations first,
AI interpretation second.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

from decision_engine import score_setup
from institutional_flow import fetch_fii_dii, summarize_flow
from intraday_intelligence import fetch_intraday
from news_intelligence import enrich_news
from options_intelligence import analyse_option_chain, fetch_option_chain
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
    """Run eight specialist agents concurrently and return one evidence pack."""
    tasks = {
        "Market Agent": lambda: {"snapshot": snapshots, "levels": levels},
        "Technical Agent": lambda: _technical(levels),
        "News Agent": lambda: enrich_news(news_items[:24]),
        "Institutional Agent": lambda: _institutional(),
        "Options Agent": lambda: _options(),
        "Intraday Agent": lambda: fetch_intraday(),
        "Sector Agent": lambda: {"sectors": sectors},
        "Watchlist Agent": lambda: rank_watchlist(watchlist, news_items[:24]),
        "Risk Agent": lambda: _risk(levels, snapshots, sectors),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix="mp-agent") as pool:
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


def _institutional():
    result = fetch_fii_dii()
    return summarize_flow(result)


def _options():
    result = fetch_option_chain("NIFTY")
    summary = analyse_option_chain(result)
    if not summary.get("available"):
        return summary
    # Keep the inter-agent packet JSON-friendly; the page-specific engine still
    # has access to the full DataFrames when it fetches options directly.
    return {
        "available": True,
        "symbol": summary.get("symbol"),
        "expiry": summary.get("expiry"),
        "spot": summary.get("spot"),
        "atm": summary.get("atm"),
        "pcr_oi": summary.get("pcr_oi"),
        "pcr_volume": summary.get("pcr_volume"),
        "max_pain": summary.get("max_pain"),
        "oi_bias": summary.get("oi_bias"),
        "source": summary.get("source"),
        "source_url": summary.get("source_url"),
        "call_resistance": summary["call_resistance"].to_dict("records"),
        "put_support": summary["put_support"].to_dict("records"),
    }


def _technical(levels):
    if not levels:
        return {"status": "INSUFFICIENT DATA"}
    close = levels.get("NIFTY close")
    sma20 = levels.get("20D SMA")
    sma50 = levels.get("50D SMA")
    return {
        "trend_vs_20d": "ABOVE" if close is not None and sma20 and close > sma20 else "BELOW" if close is not None and sma20 else "UNKNOWN",
        "trend_vs_50d": "ABOVE" if close is not None and sma50 and close > sma50 else "BELOW" if close is not None and sma50 else "UNKNOWN",
        "rsi14": levels.get("RSI14"),
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
