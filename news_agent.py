"""MarketPilot autonomous article-reading agent.

The agent opens the publisher article, extracts the article body, and uses the
configured Gemini model to produce two factual key points. It never uses the
Google News boilerplate as article context and never fills missing facts by
inference.
"""

import html
import json
import os
import re
from functools import lru_cache
from html.parser import HTMLParser

import requests

MODEL = "gemini-2.5-flash"

_GENERIC = (
    "comprehensive up-to-date news coverage",
    "aggregated from sources all over the world by google news",
    "latest news and updates from around the world",
    "news coverage from around the world",
)


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = []
        self.paragraphs = []
        self._skip = 0
        self._tag_stack = []
        self._p = None
        self._main_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form"}:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "title":
            self._tag_stack.append("title")
        elif tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").lower()
            value = attrs.get("content") or ""
            if key in {"description", "og:description", "twitter:description"} and value:
                self.meta.append(value)
        elif tag in {"main", "article"}:
            self._main_depth += 1
        elif tag == "p":
            self._p = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form"} and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag == "title" and self._tag_stack:
            self._tag_stack.pop()
        elif tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        elif tag == "p" and self._p is not None:
            text = re.sub(r"\s+", " ", " ".join(self._p)).strip()
            if 70 <= len(text) <= 3000:
                self.paragraphs.append(text)
            self._p = None

    def handle_data(self, data):
        if self._skip:
            return
        data = data.strip()
        if not data:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self.title = re.sub(r"\s+", " ", data).strip()
        if self._p is not None:
            self._p.append(data)


def _clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def _generic(text):
    low = _clean(text).lower()
    return any(p in low for p in _GENERIC)


def _dedupe(paragraphs):
    out = []
    seen = set()
    for p in paragraphs:
        key = re.sub(r"[^a-z0-9]", "", p.lower())[:180]
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out


@lru_cache(maxsize=128)
def read_article(url):
    """Open the supplied article URL and return publisher text."""
    if not url:
        return {"ok": False, "text": "", "final_url": "", "title": ""}
    try:
        r = requests.get(
            url,
            timeout=10,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-IN,en;q=0.9",
            },
        )
        if r.status_code >= 400 or not r.text:
            return {"ok": False, "text": "", "final_url": r.url, "title": ""}
        parser = _Reader()
        parser.feed(r.text[:2_500_000])
        paragraphs = _dedupe(parser.paragraphs)
        paragraphs = [p for p in paragraphs if not _generic(p)]
        if not paragraphs:
            meta = [m for m in parser.meta if not _generic(m)]
            paragraphs = meta
        text = "\n".join(paragraphs[:24])
        return {"ok": bool(text), "text": text[:30_000], "final_url": r.url, "title": parser.title}
    except Exception:
        return {"ok": False, "text": "", "final_url": "", "title": ""}


def _extract_json(text):
    try:
        return json.loads(text.strip())
    except Exception:
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _fallback_points(article_text, headline):
    """Conservative fallback when Gemini is unavailable."""
    points = []
    for p in article_text.splitlines():
        p = _clean(p)
        if len(p) < 70 or _generic(p):
            continue
        if headline and p.lower() == headline.lower():
            continue
        points.append(p)
        if len(points) == 2:
            break
    return points


def _gemini_points(headline, publisher, article_text):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or not article_text:
        return []
    try:
        from google import genai

        client = genai.Client(api_key=key)
        prompt = f"""You are the MarketPilot Article Reader agent.
Read the publisher article text below and identify exactly TWO concise key points
that are explicitly supported by the article. These should be useful facts about
what happened, numbers, causes, companies, sectors, policy actions, or market
impact. Do not repeat the headline. Do not use knowledge outside the supplied
article. Do not speculate. If the article does not contain two factual points,
return only the points that are actually supported.

Return JSON only: {{"key_points":["...","..."]}}

HEADLINE: {headline}
PUBLISHER: {publisher}
ARTICLE TEXT:
{article_text[:24000]}
"""
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"temperature": 0.1, "response_mime_type": "application/json"},
        )
        data = _extract_json(response.text or "") or {}
        points = data.get("key_points", [])
        if not isinstance(points, list):
            return []
        clean = []
        for p in points[:2]:
            p = _clean(p)
            if len(p) >= 25 and not _generic(p) and p.lower() != (headline or "").lower():
                clean.append(p[:300])
        return clean
    except Exception:
        return []


@lru_cache(maxsize=128)
def analyze_article(url, headline, publisher=""):
    """Run the article-reading agent for one story."""
    article = read_article(url)
    if not article["ok"]:
        return {"key_points": [], "status": "ARTICLE_UNAVAILABLE", "source_url": article["final_url"]}
    points = _gemini_points(headline, publisher, article["text"])
    if not points:
        points = _fallback_points(article["text"], headline)
        status = "ARTICLE_READ_FALLBACK" if points else "ARTICLE_FACTS_UNAVAILABLE"
    else:
        status = "ARTICLE_READ_BY_AI"
    return {"key_points": points[:2], "status": status, "source_url": article["final_url"]}
