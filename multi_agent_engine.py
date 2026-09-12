"""MarketPilot multi-agent report runner.

This is the parallel execution path used by the scheduled pre-market report.
The existing engine functions remain the source of truth for calculations; this
runner delegates independent investigations to specialist agents and then sends
one combined evidence packet to the Chief Intelligence AI.
"""

import json
from datetime import datetime

import engine
from agent_orchestrator import run_specialists
from ai_brain import analyze
from decision_engine import score_setup


def run():
    now = datetime.now(engine.IST)
    force_test = engine.os.getenv("FORCE_MARKET_ANALYSIS", "0").strip() == "1"

    if not engine.is_nse_trading_day(now.date()) and not force_test:
        engine.write_closed_report(
            f"NSE cash market is closed today ({now.strftime('%A, %d %B %Y')}). No pre-market trading analysis was generated."
        )
        return

    snapshots = engine.market_snapshot()
    levels = engine.nifty_technicals()
    verdict, confidence, reasons = engine.rule_bias(levels, snapshots)
    news = engine.news_items()
    watchlist = engine.watchlist_snapshot()
    sectors = engine.sector_snapshot()

    specialists = run_specialists(
        levels=levels,
        snapshots=snapshots,
        sectors=sectors,
        watchlist=watchlist,
        news_items=news,
    )

    news_agent = specialists["agents"].get("News Agent", {}).get("data", news)
    watchlist_agent = specialists["agents"].get("Watchlist Agent", {}).get("data", [])
    if isinstance(news_agent, list):
        news = news_agent
    if isinstance(watchlist_agent, list):
        watchlist_intelligence = watchlist_agent
    else:
        watchlist_intelligence = engine.rank_watchlist(watchlist, news)

    decision = score_setup(levels, snapshots, sectors, news)
    payload = {
        "date_ist": now.strftime("%Y-%m-%d"),
        "test_mode": force_test,
        "rule_bias": verdict,
        "rule_confidence": confidence,
        "signals": reasons,
        "levels": levels,
        "market_snapshot": snapshots,
        "sectors": sectors,
        "news": news,
        "watchlist": watchlist,
        "watchlist_intelligence": watchlist_intelligence,
        "decision": decision,
        "specialist_agents": specialists,
    }

    ai_result = analyze(payload)
    if force_test:
        ai_result["test_mode"] = True
        ai_result["status"] = "AI TEST ANALYSIS"

    report = {
        "date_ist": now.strftime("%Y-%m-%d"),
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_status": "AI TEST MODE" if force_test else "PRE-MARKET INTELLIGENCE",
        "verdict": verdict,
        "confidence": confidence,
        "summary": f"Parallel specialist agents produced the evidence pack. Rule-based evidence suggests a {verdict.lower()} starting framework.",
        "signals": reasons,
        "levels": levels,
        "global": snapshots,
        "news": news,
        "watchlist": watchlist,
        "watchlist_intelligence": watchlist_intelligence,
        "sectors": sectors,
        "decision": decision,
        "specialist_agents": specialists,
        "ai_analysis": ai_result,
    }
    engine.OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not force_test:
        engine.append_history(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
