"""MarketPilot decision engine.

Converts the existing evidence pack into a transparent 0-100 market setup score.
This is decision support, not a trading signal or probability forecast.
"""


def clamp(value, low=0, high=100):
    return max(low, min(high, float(value)))


def score_setup(levels, snapshots, sectors, news):
    """Return a transparent setup score and the evidence behind it."""
    score = 50.0
    factors = []
    up = down = 0

    if levels:
        close = levels.get("NIFTY close")
        sma20 = levels.get("20D SMA")
        sma50 = levels.get("50D SMA")
        ret20 = levels.get("20D return %", 0) or 0
        rsi = levels.get("RSI14")

        if close is not None and sma20:
            if close > sma20:
                score += 8; up += 1; factors.append("NIFTY above 20D SMA")
            else:
                score -= 8; down += 1; factors.append("NIFTY below 20D SMA")

        if close is not None and sma50:
            if close > sma50:
                score += 5; up += 1; factors.append("NIFTY above 50D SMA")
            else:
                score -= 5; down += 1; factors.append("NIFTY below 50D SMA")

        if ret20 > 2:
            score += 7; up += 1; factors.append("20D momentum positive")
        elif ret20 < -2:
            score -= 7; down += 1; factors.append("20D momentum negative")

        if rsi is not None:
            if 55 <= rsi <= 68:
                score += 5; up += 1; factors.append("RSI in constructive momentum zone")
            elif rsi < 40:
                score -= 5; down += 1; factors.append("RSI signals weak momentum")
            elif rsi > 72:
                score -= 3; down += 1; factors.append("RSI indicates stretched conditions")

    by_name = {x.get("name"): x for x in snapshots or []}
    nifty = by_name.get("NIFTY 50", {})
    bank = by_name.get("BANK NIFTY", {})
    vix = by_name.get("INDIA VIX", {})

    if bank and nifty:
        spread = (bank.get("change_pct", 0) or 0) - (nifty.get("change_pct", 0) or 0)
        if spread > 0.35:
            score += 6; up += 1; factors.append("Bank Nifty is outperforming")
        elif spread < -0.35:
            score -= 6; down += 1; factors.append("Bank Nifty is underperforming")

    if vix:
        vix_change = vix.get("change_pct", 0) or 0
        if vix_change >= 5:
            score -= 8; down += 1; factors.append("India VIX rising sharply")
        elif vix_change <= -3:
            score += 4; up += 1; factors.append("India VIX easing")

    sector_changes = [s.get("avg_change_pct") for s in sectors or [] if s.get("avg_change_pct") is not None]
    if sector_changes:
        breadth = sum(x > 0 for x in sector_changes) / len(sector_changes)
        if breadth >= 0.67:
            score += 5; up += 1; factors.append("Broad sector participation is positive")
        elif breadth <= 0.33:
            score -= 5; down += 1; factors.append("Sector participation is weak")

    positive_news = sum(1 for x in news or [] if x.get("impact") == "POSITIVE")
    negative_news = sum(1 for x in news or [] if x.get("impact") == "NEGATIVE")
    if positive_news >= negative_news + 3:
        score += 4; up += 1; factors.append("News tone is net positive")
    elif negative_news >= positive_news + 3:
        score -= 4; down += 1; factors.append("News tone is net negative")

    score = round(clamp(score), 1)
    if score >= 65:
        bias = "BULLISH"
    elif score <= 35:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    confidence = "HIGH" if abs(score - 50) >= 20 and abs(up - down) >= 3 else "MEDIUM" if abs(score - 50) >= 10 else "LOW"

    if score >= 75:
        regime = "STRONG TREND"
    elif score >= 60:
        regime = "BULLISH LEAN"
    elif score <= 25:
        regime = "STRONG DOWNTREND"
    elif score <= 40:
        regime = "BEARISH LEAN"
    else:
        regime = "MIXED / RANGE"

    bull_trigger = "NIFTY holds above its 20D SMA and Bank Nifty confirms strength."
    bear_trigger = "NIFTY loses its 20D SMA while volatility expands."
    invalidation = "The morning view is invalidated when the price structure and volatility move materially against the evidence pack."

    return {
        "score": score,
        "bias": bias,
        "confidence": confidence,
        "regime": regime,
        "positive_factors": up,
        "negative_factors": down,
        "evidence": factors[:10],
        "bull_trigger": bull_trigger,
        "bear_trigger": bear_trigger,
        "invalidation": invalidation,
        "methodology": "Transparent rule-weighted evidence score. It is not a probability and does not imply a guaranteed market direction.",
    }
