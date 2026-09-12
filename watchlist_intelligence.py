"""MarketPilot watchlist intelligence.

Ranks watched equities using momentum, trend, volume, RSI and evidence-aware
news. Scores are research heuristics, not price targets or trading instructions.
"""


def _clamp(value, low=0, high=100):
    return max(low, min(high, float(value)))


def _news_for_stock(ticker, news):
    name = ticker.replace(".NS", "").upper()
    matches = []
    for item in news or []:
        text = f"{item.get('title', '')} {item.get('affected', '')}".upper()
        if name in text:
            matches.append(item)
    return matches


def rank_watchlist(rows, news=None):
    """Return watchlist rows enriched with an evidence-aware research score."""
    ranked = []
    for row in rows or []:
        stock = str(row.get("ticker") or row.get("Stock") or "").replace(".NS", "").upper()
        day = float(row.get("change_pct", row.get("1D %", 0)) or 0)
        ret20 = float(row.get("20D_return_pct", row.get("20D %", 0)) or 0)
        sma = float(row.get("vs_20D_SMA_pct", row.get("vs 20D SMA %", 0)) or 0)
        volume = float(row.get("volume_vs_20D", row.get("Vol / 20D", 1)) or 1)
        rsi = row.get("RSI14")
        rsi = float(rsi) if rsi is not None else None

        score = 50.0
        reasons = []

        # Trend and momentum: 45 points of the framework.
        if sma > 2:
            score += 12; reasons.append("above 20D SMA")
        elif sma > 0:
            score += 7; reasons.append("holding above 20D SMA")
        elif sma < -2:
            score -= 12; reasons.append("below 20D SMA")
        else:
            score -= 6; reasons.append("near/below 20D SMA")

        if ret20 > 5:
            score += 10; reasons.append("strong 20D momentum")
        elif ret20 > 0:
            score += 5; reasons.append("positive 20D momentum")
        elif ret20 < -5:
            score -= 10; reasons.append("weak 20D momentum")
        elif ret20 < 0:
            score -= 5; reasons.append("negative 20D momentum")

        if day > 1:
            score += 5; reasons.append("positive latest session")
        elif day < -1:
            score -= 5; reasons.append("negative latest session")

        # Volume confirmation: 15 points.
        if volume >= 1.5 and day > 0:
            score += 8; reasons.append("high volume confirms upside")
        elif volume >= 1.5 and day < 0:
            score -= 8; reasons.append("high volume confirms downside")
        elif volume >= 1.1:
            score += 2; reasons.append("above-average volume")

        # RSI: avoid rewarding extreme overbought readings.
        if rsi is not None:
            if 55 <= rsi <= 68:
                score += 7; reasons.append("constructive RSI")
            elif 68 < rsi <= 72:
                score += 2; reasons.append("strong but warm RSI")
            elif rsi > 72:
                score -= 5; reasons.append("overbought RSI")
            elif rsi < 35:
                score -= 4; reasons.append("weak RSI")

        # Evidence-aware company news: maximum ±15.
        company_news = _news_for_stock(stock, news)
        news_score = 0.0
        positive = negative = 0
        supported = 0
        for item in company_news:
            status = item.get("claim_status", "INSUFFICIENT EVIDENCE")
            weight = 0.0 if status == "DISPUTED" else 1.0 if status == "SUPPORTED" else 0.75 if status == "CORROBORATED" else 0.2
            impact = item.get("impact")
            if impact == "POSITIVE": news_score += weight; positive += 1
            elif impact == "NEGATIVE": news_score -= weight; negative += 1
            if status in ("SUPPORTED", "CORROBORATED"): supported += 1
        score += _clamp(news_score * 3, -15, 15)
        if company_news:
            reasons.append(f"{len(company_news)} linked news item(s), {supported} supported/corroborated")

        score = round(_clamp(score), 1)
        if score >= 72:
            label = "TOP OPPORTUNITY"
        elif score >= 58:
            label = "WATCH"
        elif score <= 38:
            label = "RISK"
        else:
            label = "NEUTRAL"

        confidence = "HIGH" if (volume >= 1.5 and abs(day) > 1 and rsi is not None) else "MEDIUM" if rsi is not None else "LOW"
        ranked.append({
            **row,
            "ticker": stock,
            "research_score": score,
            "research_label": label,
            "research_confidence": confidence,
            "research_reasons": reasons[:5],
            "linked_news": len(company_news),
            "supported_news": supported,
            "positive_news": positive,
            "negative_news": negative,
        })

    return sorted(ranked, key=lambda x: x["research_score"], reverse=True)
