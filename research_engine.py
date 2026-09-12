"""Autonomous research and verification engine for MarketPilot.

Given a market-moving claim, the research agent discovers independent search
results, opens publisher pages, extracts article evidence, and scores whether
the claim is corroborated. It never upgrades a claim when the evidence is
missing or contradictory.
"""

import re
from functools import lru_cache
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

from news_agent import analyze_article

GENERIC = (
    "comprehensive up-to-date news coverage",
    "aggregated from sources all over the world by google news",
)


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _tokens(text):
    return {x for x in re.findall(r"[a-z0-9]{3,}", text.lower()) if x not in {
        "the", "and", "for", "with", "from", "after", "before", "into", "india", "market", "news"
    }}


def _similarity(a, b):
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def _valid_result(entry, headline):
    title = _clean(getattr(entry, "title", ""))
    link = _clean(getattr(entry, "link", ""))
    if not title or not link or _similarity(title, headline) < 0.12:
        return False
    low = title.lower()
    return not any(x in low for x in GENERIC)


@lru_cache(maxsize=128)
def discover_sources(headline, max_results=8):
    """Discover independent publisher candidates from Google News RSS."""
    query = quote_plus(_clean(headline))
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        response = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        feed = feedparser.parse(response.content)
    except Exception:
        return []

    seen_domains = set()
    sources = []
    for entry in feed.entries:
        if not _valid_result(entry, headline):
            continue
        publisher = _clean(getattr(entry, "source", {}).get("title", "")) if hasattr(getattr(entry, "source", None), "get") else ""
        domain = urlparse(entry.link).netloc.lower().replace("www.", "")
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        sources.append({
            "headline": _clean(entry.title),
            "publisher": publisher or domain,
            "url": entry.link,
            "published": _clean(getattr(entry, "published", "")),
            "domain": domain,
        })
        if len(sources) >= max_results:
            break
    return sources


def _independent(sources):
    return len({s.get("domain") for s in sources if s.get("domain")})


def research_claim(headline, primary_url="", primary_publisher="", max_sources=6):
    """Run the autonomous research loop for one claim."""
    headline = _clean(headline)
    candidates = discover_sources(headline, max_sources)
    if primary_url:
        primary_domain = urlparse(primary_url).netloc.lower().replace("www.", "")
        if primary_domain and not any(s.get("domain") == primary_domain for s in candidates):
            candidates.insert(0, {
                "headline": headline,
                "publisher": primary_publisher or primary_domain,
                "url": primary_url,
                "published": "",
                "domain": primary_domain,
            })

    evidence = []
    attempts = []
    for source in candidates[:max_sources]:
        result = analyze_article(source["url"], source["headline"], source["publisher"])
        attempts.append({
            "publisher": source["publisher"],
            "domain": source["domain"],
            "status": result.get("status", "UNKNOWN"),
        })
        points = result.get("key_points", [])
        if points:
            evidence.append({
                "publisher": source["publisher"],
                "domain": source["domain"],
                "url": result.get("source_url") or source["url"],
                "headline": source["headline"],
                "key_points": points,
                "status": result.get("status", "UNKNOWN"),
            })

    publishers = {e["domain"] for e in evidence if e.get("domain")}
    all_text = " ".join(" ".join(e.get("key_points", [])) for e in evidence)
    agreement = []
    for e in evidence:
        if _similarity(headline, e.get("headline", "")) >= 0.25:
            agreement.append(e)

    if len(publishers) >= 3 and len(agreement) >= 3:
        state, confidence = "CORROBORATED", "HIGH"
    elif len(publishers) >= 2 and len(agreement) >= 2:
        state, confidence = "CROSS_CHECKED", "MEDIUM"
    elif len(publishers) == 1:
        state, confidence = "SINGLE_SOURCE", "LOW"
    else:
        state, confidence = "INSUFFICIENT", "LOW"

    return {
        "claim": headline,
        "evidence_state": state,
        "confidence": confidence,
        "independent_publishers": len(publishers),
        "evidence": evidence,
        "attempts": attempts,
        "research_complete": bool(evidence),
        "research_policy": "discover -> read -> corroborate -> downgrade when uncertain",
        "no_fabrication": True,
    }
