"""MarketPilot decision engine.

Converts the evidence pack into a transparent 0-100 market setup score.
News is weighted by claim status so unverified headlines do not influence the
score as strongly as independently supported reporting.
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

    # Evidence-aware news weighting.
    # Supported/corroborated stories get full weight; insufficient evidence gets
    # only a small influence; disputed stories are ignored rather than treated
    # as directional truth.
    supported_positive = supported_negative = 0.0
    disputed = insufficient = 0
    for item in news or []:
        status = item.get("claim_status", "INSUFFICIENT EVIDENCE")
        impact = item.get("impact")
        if status == "DISPUTED":
            disputed += 1
            continue
        if status == "SUPPORTED":
            weight = 1.0
        elif status == "CORROBORATED":
            weight = 0.85
        else:
            weight = 0.25
            insufficient += 1
        if impact == "POSITIVE":
            supported_positive += weight
        elif impact == "NEGATIVE":
            supported_negative += weight

    news_balance = supported_positive - supported_negative
    if news_balance >= 3:
        score += 4; up += 1; factors.append("Evidence-weighted news tone is net positive")
    elif news_balance <= -3:
        score -= 4; down += 1; factors.append("Evidence-weighted news tone is net negative")
    elif supported_positive or supported_negative:
        factors.append("News tone is mixed after evidence weighting")

    if disputed:
        factors.append(f"{disputed} disputed news claim(s) excluded from directional scoring")
    if insufficient:
        factors.append(f"{insufficient} insufficient-evidence story/stories given reduced weight")

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

    return {
        "score": score,
        "bias": bias,
        "confidence": confidence,
        "regime": regime,
        "positive_factors": up,
        "negative_factors": down,
        "evidence": factors[:10],
        "bull_trigger": "NIFTY holds above its 20D SMA and Bank Nifty confirms strength.",
        "bear_trigger": "NIFTY loses its 20D SMA while volatility expands.",
        "invalidation": "The market view is invalidated when price structure and volatility move materially against the evidence pack.",
        "methodology": "Transparent rule-weighted evidence score. News direction is weighted by claim status; disputed claims are excluded and insufficient-evidence claims receive reduced weight. This is not a probability or trading recommendation.",
    }
