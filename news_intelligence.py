"""MarketPilot news intelligence helpers.

Turns RSS headlines into cautious, evidence-based metadata. Google News is an
aggregator, so publisher attribution is taken from the RSS source metadata or
from the trailing publisher suffix in the headline rather than the Google
redirect hostname.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse
import re


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
        return host or ""
    except Exception:
        return ""


def publisher_from_title(title: str) -> tuple[str, str]:
    """Google News commonly appends ' - Publisher' to RSS titles."""
    text = (title or "").strip()
    match = re.search(r"\s+-\s+([^-]+)$", text)
    if not match:
        return text, ""
    publisher = match.group(1).strip()
    headline = text[:match.start()].strip()
    return headline or text, publisher


def publisher_identity(item: dict) -> tuple[str, str, str]:
    """Return headline, publisher name and publisher domain.

    Prefer an RSS source element when available, otherwise use the publisher
    suffix Google News appends to the title. Never treat news.google.com as the
    publisher.
    """
    raw_title = item.get("title", "").strip()
    headline, title_publisher = publisher_from_title(raw_title)

    source = item.get("source")
    if isinstance(source, dict):
        source_name = str(source.get("title") or source.get("name") or "").strip()
        source_url = str(source.get("url") or "").strip()
    else:
        source_name = str(source or "").strip()
        source_url = ""

    name = source_name or title_publisher or "Unknown publisher"
    domain = publisher_domain(source_url)
    if not domain or domain == "news.google.com":
        # Best-effort domain from the known publisher name. The Google redirect
        # itself is intentionally never presented as the publisher.
        slug = re.sub(r"[^a-z0-9]+", "", name.lower())
        known = {
            "reuters": "reuters.com",
            "businessstandard": "business-standard.com",
            "economictimes": "economictimes.indiatimes.com",
            "moneycontrol": "moneycontrol.com",
            "livemint": "livemint.com",
            "ndtvprofit": "ndtvprofit.com",
            "hindustantimes": "hindustantimes.com",
            "theeconomicstimes": "economictimes.indiatimes.com",
            "cnbctv18": "cnbctv18.com",
            "financialexpress": "financialexpress.com",
            "thehindubusinessline": "thehindubusinessline.com",
            "mint": "livemint.com",
        }
        domain = known.get(slug, "")

    return headline, name, domain


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
    normalized_titles = [publisher_from_title(x.get("title", ""))[0] for x in items]
    for i, title in enumerate(normalized_titles):
        placed = False
        for cluster in clusters:
            rep = normalized_titles[cluster[0]]
            if similarity(title, rep) >= 0.24:
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
        headline, publisher_name, domain = publisher_identity(item)
        cluster_id, cluster = cluster_by_item[idx]
        domains = set()
        publisher_names = set()
        for j in cluster:
            _, n, d = publisher_identity(items[j])
            if d:
                domains.add(d)
            if n:
                publisher_names.add(n)

        if len(domains) >= 2:
            verification = "CORROBORATED"
            verification_label = "✅ CORROBORATED"
            verification_detail = f"Similar reporting found across {len(domains)} publisher domains."
        elif len(publisher_names) >= 2:
            verification = "CORROBORATED"
            verification_label = "✅ CORROBORATED"
            verification_detail = f"Similar reporting found from {len(publisher_names)} publisher names."
        elif publisher_name != "Unknown publisher":
            verification = "SINGLE_SOURCE"
            verification_label = "⚠️ SINGLE SOURCE"
            verification_detail = "Only one publisher currently carries this story cluster."
        else:
            verification = "UNVERIFIED"
            verification_label = "⚠️ UNVERIFIED"
            verification_detail = "Publisher could not be established from the feed metadata or headline."

        impact, impact_reason = classify_impact(headline)
        affected = infer_affected(headline)

        enriched.append({
            **item,
            "title": headline,
            "publisher": publisher_name,
            "publisher_domain": domain,
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
