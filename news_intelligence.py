"""MarketPilot news intelligence helpers.

Turns RSS headlines into cautious, evidence-based metadata without claiming
that a headline is factually true. Verification means corroboration across
independent publisher domains, not repetition inside one feed.
"""

from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse


IMPACT_RULES = {
    "POSITIVE": {
        "words": {"beats", "strong", "surge", "rises", "raised", "upgrade", "approval", "wins", "order", "growth", "record", "inflows", "cut", "easing"},
        "market_words": {"rate cut", "stimulus", "inflation cools", "gdp growth"},
    },
    "NEGATIVE": {
        "words": {"falls", "misses", "weak", "downgrade", "probe", "fraud", "ban", "default", "cuts", "loss", "outflows", "war", "tariff", "sanction", "inflation"},
        "market_words": {"rate hike", "recession", "default", "geopolitical escalation"},
    },
}


def publisher_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


def normalized_words(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch == " " else " " for ch in (text or ""))
    return set(cleaned.split())


def similarity(a: str, b: str) -> float:
    wa, wb = normalized_words(a), normalized_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(1, len(wa | wb))


def cluster_headlines(items: list[dict]) -> list[list[int]]:
    clusters: list[list[int]] = []
    for i, item in enumerate(items):
        placed = False
        for cluster in clusters:
            rep = items[cluster[0]].get("title", "")
            if similarity(item.get("title", ""), rep) >= 0.24:
                cluster.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
    return clusters


def classify_impact(title: str) -> tuple[str, str]:
    text = (title or "").lower()
    pos_hits = sum(1 for word in IMPACT_RULES["POSITIVE"]["words"] if word in text)
    neg_hits = sum(1 for word in IMPACT_RULES["NEGATIVE"]["words"] if word in text)
    if any(phrase in text for phrase in IMPACT_RULES["POSITIVE"]["market_words"]):
        pos_hits += 2
    if any(phrase in text for phrase in IMPACT_RULES["NEGATIVE"]["market_words"]):
        neg_hits += 2

    if pos_hits > neg_hits and pos_hits:
        return "POSITIVE", "Headline language contains more positive market-impact signals."
    if neg_hits > pos_hits and neg_hits:
        return "NEGATIVE", "Headline language contains more negative market-impact signals."
    return "NEUTRAL", "No clear directional impact can be established from the headline alone."


def infer_affected(title: str) -> str:
    text = (title or "").lower()
    mapping = {
        "BANKING": {"bank", "rbi", "credit", "nbfc", "loan", "rate"},
        "IT": {"it", "software", "infosys", "tcs", "wipro", "tech"},
        "ENERGY": {"oil", "crude", "energy", "reliance", "ongc", "gas"},
        "AUTO": {"auto", "car", "vehicle", "tata motors", "mahindra", "maruti"},
        "PHARMA": {"pharma", "drug", "fda", "sun pharma", "dr reddy"},
        "METALS": {"steel", "metal", "aluminium", "copper"},
        "FMCG": {"fmcg", "itc", "hindustan unilever", "consumer"},
    }
    scores = {sector: sum(1 for token in tokens if token in text) for sector, tokens in mapping.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "MARKET"


def enrich_news(items: list[dict]) -> list[dict]:
    if not items:
        return []

    clusters = cluster_headlines(items)
    cluster_by_item = {}
    for cluster_id, cluster in enumerate(clusters, start=1):
        for idx in cluster:
            cluster_by_item[idx] = (cluster_id, cluster)

    enriched = []
    for idx, item in enumerate(items):
        title = item.get("title", "").strip()
        domain = publisher_domain(item.get("link", ""))
        cluster_id, cluster = cluster_by_item[idx]
        domains = {publisher_domain(items[j].get("link", "")) for j in cluster}
        domains.discard("unknown")

        if len(domains) >= 2:
            verification = "CORROBORATED"
            verification_label = "✅ CORROBORATED"
            verification_detail = f"Similar reporting found across {len(domains)} publisher domains."
        elif len(domains) == 1:
            verification = "SINGLE_SOURCE"
            verification_label = "⚠️ SINGLE SOURCE"
            verification_detail = "Only one publisher domain currently carries this story cluster."
        else:
            verification = "UNVERIFIED"
            verification_label = "⚠️ UNVERIFIED"
            verification_detail = "Publisher could not be established from the feed link."

        impact, impact_reason = classify_impact(title)
        affected = infer_affected(title)

        enriched.append({
            **item,
            "publisher": domain,
            "cluster_id": cluster_id,
            "verification": verification,
            "verification_label": verification_label,
            "verification_detail": verification_detail,
            "impact": impact,
            "impact_reason": impact_reason,
            "affected": affected,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        })

    return enriched
