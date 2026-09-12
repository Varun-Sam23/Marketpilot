"""MarketPilot market-regime classifier.

Classifies NIFTY market structure from trend, momentum, range position and
volatility. Outputs are research heuristics, not forecasts or trading signals.
"""


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def classify_regime(levels, vix_change=0.0):
    """Return a transparent regime classification from a technical snapshot."""
    levels = levels or {}
    close = levels.get("NIFTY close")
    sma20 = levels.get("20D SMA")
    sma50 = levels.get("50D SMA")
    ret20 = float(levels.get("20D return %", 0) or 0)
    rsi = levels.get("RSI14")
    range_pos = float(levels.get("range_position_%", 50) or 50)

    if close is None or sma20 is None or sma50 is None:
        return {
            "regime": "INSUFFICIENT DATA", "score": 50.0, "trend": "UNKNOWN",
            "volatility": "UNKNOWN", "confidence": "LOW", "reasons": ["Technical snapshot is incomplete."],
            "playbook": "Wait for enough market structure data before interpreting the regime.",
        }

    trend_score = 0.0
    reasons = []
    if close > sma20:
        trend_score += 1; reasons.append("NIFTY is above the 20D SMA")
    else:
        trend_score -= 1; reasons.append("NIFTY is below the 20D SMA")
    if close > sma50:
        trend_score += 1; reasons.append("NIFTY is above the 50D SMA")
    else:
        trend_score -= 1; reasons.append("NIFTY is below the 50D SMA")
    if sma20 > sma50:
        trend_score += 1; reasons.append("20D SMA is above 50D SMA")
    else:
        trend_score -= 1; reasons.append("20D SMA is below 50D SMA")

    if ret20 >= 5:
        trend_score += 1; reasons.append("20D momentum is strong")
    elif ret20 > 1:
        trend_score += 0.5; reasons.append("20D momentum is positive")
    elif ret20 <= -5:
        trend_score -= 1; reasons.append("20D momentum is weak")
    elif ret20 < -1:
        trend_score -= 0.5; reasons.append("20D momentum is negative")

    if trend_score >= 3:
        trend = "STRONG UPTREND"
    elif trend_score >= 1:
        trend = "UPTREND"
    elif trend_score <= -3:
        trend = "STRONG DOWNTREND"
    elif trend_score <= -1:
        trend = "DOWNTREND"
    else:
        trend = "RANGE / TRANSITION"

    high_vol = float(vix_change or 0) >= 5
    low_vol = float(vix_change or 0) <= -3
    if high_vol:
        volatility = "EXPANDING"
        reasons.append("India VIX is rising sharply")
    elif low_vol:
        volatility = "EASING"
        reasons.append("India VIX is easing")
    else:
        volatility = "STABLE"

    if high_vol and trend in ("UPTREND", "STRONG UPTREND"):
        regime = "VOLATILE UPTREND"
    elif high_vol and trend in ("DOWNTREND", "STRONG DOWNTREND"):
        regime = "VOLATILE DOWNTREND"
    elif high_vol:
        regime = "HIGH-VOLATILITY RANGE"
    else:
        regime = trend

    score = 50 + trend_score * 10
    if range_pos >= 80 and ret20 > 0:
        score += 5; reasons.append("Price is near the upper end of its 20D range")
    elif range_pos <= 20 and ret20 < 0:
        score -= 5; reasons.append("Price is near the lower end of its 20D range")
    if rsi is not None:
        rsi = float(rsi)
        if 55 <= rsi <= 68:
            reasons.append("RSI supports constructive momentum")
        elif rsi > 72:
            score -= 4; reasons.append("RSI is stretched above 72")
        elif rsi < 35:
            score += 2; reasons.append("RSI is deeply weak, increasing rebound risk")

    if high_vol:
        score -= 5
    score = round(_clamp(score), 1)
    confidence = "HIGH" if len(reasons) >= 5 and abs(trend_score) >= 2 else "MEDIUM" if abs(trend_score) >= 1 else "LOW"

    playbooks = {
        "STRONG UPTREND": "Favor trend-following research; prioritize strength, pullback quality and confirmation over chasing extended moves.",
        "UPTREND": "Favor selective long-bias research while requiring confirmation near resistance and avoiding weak setups.",
        "VOLATILE UPTREND": "Trend is positive but risk is elevated; demand wider confirmation and treat position sizing as a risk variable.",
        "RANGE / TRANSITION": "Prioritize support/resistance, breakouts and failed-breakout evidence; avoid assuming trend continuation.",
        "HIGH-VOLATILITY RANGE": "Reduce conviction; wait for volatility to contract or for a confirmed range break.",
        "DOWNTREND": "Prioritize capital preservation and relative strength; treat rallies as unconfirmed until structure improves.",
        "STRONG DOWNTREND": "Bearish structure dominates; avoid interpreting oversold readings as automatic reversals.",
        "VOLATILE DOWNTREND": "Downtrend plus expanding volatility is the highest-risk regime; require strong confirmation before acting on any bullish thesis.",
    }

    return {
        "regime": regime, "score": score, "trend": trend, "volatility": volatility,
        "confidence": confidence, "reasons": reasons[:8], "playbook": playbooks.get(regime, "Wait for clearer structure."),
        "metrics": {"20D return %": ret20, "range position %": range_pos, "VIX change %": float(vix_change or 0), "RSI14": rsi},
    }
