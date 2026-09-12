from datetime import datetime, timezone
import html
import re
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urlparse, quote_plus
import feedparser
import requests

from news_agent import analyze_article

IMPACT_RULES = {
    "POSITIVE": {"words": {"beats","strong","surge","rises","raised","upgrade","approval","wins","order","growth","record","inflows","cut","easing"}, "market_words": {"rate cut","stimulus","inflation cools","gdp growth"}},
    "NEGATIVE": {"words": {"falls","misses","weak","downgrade","probe","fraud","ban","default","cuts","loss","outflows","war","tariff","sanction","inflation"}, "market_words": {"rate hike","recession","default","geopolitical escalation"}},
}


def publisher_domain(url):
    try:
        host=urlparse(url or "").netloc.lower(); return host[4:] if host.startswith("www.") else host
    except Exception: return ""


def publisher_from_title(title):
    text=(title or "").strip(); m=re.search(r"\s+-\s+([^-]+)$", text)
    if not m: return text,""
    return text[:m.start()].strip() or text,m.group(1).strip()


def publisher_identity(item):
    raw=item.get("title","").strip(); headline,title_pub=publisher_from_title(raw)
    explicit=str(item.get("publisher") or "").strip(); source=item.get("source"); source_name=""
    if isinstance(source,dict): source_name=str(source.get("title") or source.get("name") or "").strip()
    elif source and not str(source).lower().endswith("markets"): source_name=str(source).strip()
    name=explicit or source_name or title_pub or "Unknown publisher"
    if name.lower()=="news.google.com": name=title_pub or "Unknown publisher"
    known={"reuters":"reuters.com","business standard":"business-standard.com","businessstandard":"business-standard.com","economic times":"economictimes.indiatimes.com","livemint":"livemint.com","moneycontrol":"moneycontrol.com","ndtv profit":"ndtvprofit.com","cnbc tv18":"cnbctv18.com","financial express":"financialexpress.com","hindustan times":"hindustantimes.com"}
    return headline,name,known.get(name.lower(),"")


def words(text): return set(re.sub(r"[^a-z0-9 ]"," ",(text or "").lower()).split())


def similarity(a,b):
    wa,wb=words(a),words(b); return len(wa&wb)/max(1,len(wa|wb)) if wa and wb else 0


def cluster_headlines(items):
    clusters=[]; clean=[publisher_from_title(x.get("title", ""))[0] for x in items]
    for i,title in enumerate(clean):
        placed=False
        for cluster in clusters:
            if similarity(title,clean[cluster[0]])>=0.24: cluster.append(i); placed=True; break
        if not placed: clusters.append([i])
    return clusters


def classify_impact(title):
    text=(title or "").lower(); pos=sum(w in text for w in IMPACT_RULES["POSITIVE"]["words"]); neg=sum(w in text for w in IMPACT_RULES["NEGATIVE"]["words"])
    pos+=2*any(p in text for p in IMPACT_RULES["POSITIVE"]["market_words"]); neg+=2*any(p in text for p in IMPACT_RULES["NEGATIVE"]["market_words"])
    if pos>neg and pos: return "POSITIVE","Headline language contains positive market-impact signals."
    if neg>pos and neg: return "NEGATIVE","Headline language contains negative market-impact signals."
    return "NEUTRAL","No clear directional impact is established from the headline alone."


def infer_affected(title):
    text=(title or "").lower(); mapping={"BANKING":{"bank","rbi","credit","nbfc","loan","rate"},"IT":{"software","infosys","tcs","wipro","tech"},"ENERGY":{"oil","crude","energy","reliance","ongc","gas"},"AUTO":{"auto","car","vehicle","tata motors","mahindra","maruti"},"PHARMA":{"pharma","drug","fda","sun pharma","dr reddy"},"METALS":{"steel","metal","aluminium","copper"},"FMCG":{"fmcg","itc","hindustan unilever","consumer"}}
    scores={sector:sum(token in text for token in tokens) for sector,tokens in mapping.items()}; best=max(scores,key=scores.get)
    return best if scores[best] else "MARKET"


def evidence_score(verification, source_count, conflict=False):
    """Corroboration strength, not probability that a claim is true."""
    if verification=="CONFLICTING": return 35
    if verification=="CROSS_CHECKED": return min(90,55+max(0,source_count-2)*10)
    if verification=="CORROBORATED": return min(75,45+max(0,source_count-1)*10)
    if verification=="SINGLE_SOURCE": return 30
    return 10


def claim_status(verification, sources, impact_signals):
    """Conservative claim assessment. It never labels a headline TRUE solely because publishers repeat it."""
    count=len(sources); pos=impact_signals.count("POSITIVE"); neg=impact_signals.count("NEGATIVE")
    if verification=="CONFLICTING" or (pos and neg and abs(pos-neg)<=1):
        return "DISPUTED","Independent reporting exists, but the available signals disagree. Treat the claim as disputed until a primary or authoritative source resolves the conflict."
    if count>=2:
        return "SUPPORTED","The event is supported by independent publisher coverage. This supports the existence of the reported event; individual details still require primary-source confirmation."
    if count==1:
        return "INSUFFICIENT EVIDENCE","Only one additional publisher was found. The claim may be genuine, but independent evidence is not yet strong enough for a supported classification."
    return "INSUFFICIENT EVIDENCE","No independent cross-check was available. MarketPilot will not infer that the claim is true from the headline alone."


def clean_summary(value, headline):
    text=re.sub(r"<[^>]+>"," ",str(value or ""))
    text=html.unescape(text)
    text=re.sub(r"\s+"," ",text).strip(" -–—|")
    if not text or text.lower()==(headline or "").strip().lower(): return ""
    generic=("comprehensive up-to-date news coverage","aggregated from sources all over the world by google news","latest news and updates from around the world","news coverage from around the world")
    if any(p in text.lower() for p in generic): return ""
    return text


def useful_summary(text, headline):
    """Accept only useful article context; reject Google News boilerplate and headline echoes."""
    text=clean_summary(text, headline)
    if not text: return ""
    hwords=words(headline); swords=words(text)
    overlap=len(hwords & swords)/max(1,len(hwords)) if hwords else 0
    if len(swords)<8 or overlap>=0.88: return ""
    return text


class _ArticleParser(HTMLParser):
    """Small dependency-free extractor for article paragraphs and metadata."""
    def __init__(self):
        super().__init__()
        self.meta=[]; self.paragraphs=[]; self._in_p=False; self._p=[]; self._skip=0

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in {"script","style","noscript","svg"}:
            self._skip+=1; return
        if self._skip: return
        if tag=="meta":
            key=(attrs.get("name") or attrs.get("property") or "").lower(); value=attrs.get("content") or ""
            if key in {"description","og:description","twitter:description"} and value: self.meta.append(value)
        elif tag=="p": self._in_p=True; self._p=[]

    def handle_endtag(self, tag):
        if tag in {"script","style","noscript","svg"} and self._skip:
            self._skip-=1; return
        if self._skip: return
        if tag=="p" and self._in_p:
            text=re.sub(r"\s+"," "," ".join(self._p)).strip()
            if len(text)>=70: self.paragraphs.append(text)
            self._in_p=False; self._p=[]

    def handle_data(self, data):
        if not self._skip and self._in_p and data.strip(): self._p.append(data.strip())


@lru_cache(maxsize=128)
def article_key_points(url, headline):
    """Legacy deterministic extractor retained as a final fallback."""
    if not url: return ""
    try:
        response=requests.get(url,timeout=8,headers={"User-Agent":"Mozilla/5.0 (MarketPilot News Intelligence)"},allow_redirects=True)
        if response.status_code>=400 or not response.text: return ""
        parser=_ArticleParser(); parser.feed(response.text[:1500000])
        candidates=parser.meta+parser.paragraphs[:6]
        for text in candidates:
            summary=useful_summary(text,headline)
            if summary: return summary
    except Exception: pass
    return ""


@lru_cache(maxsize=128)
def story_summary(headline, current_publisher="", article_url=""):
    """Fallback search for genuine article context when the agent cannot read the link."""
    direct=article_key_points(article_url,headline)
    if direct: return direct
    try:
        query=quote_plus('"'+(headline or "")[:180]+'"'); url=f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"; feed=feedparser.parse(url); candidates=[]
        for entry in feed.entries[:8]:
            entry_title,entry_publisher=publisher_from_title(entry.get("title", "")); src=entry.get("source")
            if isinstance(src,dict): entry_publisher=str(src.get("title") or src.get("name") or entry_publisher).strip()
            entry_link=str(entry.get("link") or "")
            summary=article_key_points(entry_link,headline)
            if not summary: summary=useful_summary(entry.get("summary") or entry.get("description") or "",headline)
            if not summary: continue
            same_pub=bool(current_publisher and entry_publisher and entry_publisher.lower()==current_publisher.lower()); candidates.append((same_pub,len(summary),summary))
        if candidates:
            candidates.sort(key=lambda x:(x[0],x[1]),reverse=True); return candidates[0][2]
    except Exception: pass
    return ""


def targeted_cross_check(headline, current_publisher=""):
    try:
        query=quote_plus('"'+headline[:180]+'"'); url=f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"; feed=feedparser.parse(url); sources=[]; impacts=[]
        for entry in feed.entries[:8]:
            title,name=publisher_from_title(entry.get("title", "")); src=entry.get("source")
            if isinstance(src,dict): name=str(src.get("title") or src.get("name") or name).strip()
            if not name or name.lower()=="news.google.com" or (current_publisher and name.lower()==current_publisher.lower()) or any(name.lower()==s.lower() for s in sources): continue
            sources.append(name); impacts.append(classify_impact(title)[0])
        if len(sources)>=2:
            pos=impacts.count("POSITIVE"); neg=impacts.count("NEGATIVE")
            if pos and neg and abs(pos-neg)<=1: return "CONFLICTING","CONFLICTING REPORTS","Fresh search found independent publishers, but their headline signals conflict.",sources,impacts
            return "CROSS_CHECKED","CROSS-CHECKED",f"Fresh search found independent reporting from {len(sources)} additional publishers.",sources,impacts
        if len(sources)==1: return "SINGLE_SOURCE","SINGLE SOURCE","Only one additional publisher was found in the targeted search.",sources,impacts
    except Exception: pass
    return "UNVERIFIED","UNVERIFIED","Fresh independent cross-check was unavailable. MarketPilot will not label the claim as verified.",[],[]


def enrich_news(items):
    if not items: return []
    clusters=cluster_headlines(items); belong={i:(cid,c) for cid,c in enumerate(clusters,1) for i in c}; out=[]
    for idx,item in enumerate(items):
        headline,name,domain=publisher_identity(item); cid,cluster=belong[idx]; domains=set(); names=set()
        for j in cluster:
            _,n,d=publisher_identity(items[j])
            if d: domains.add(d)
            if n and n!="Unknown publisher": names.add(n)
        if len(domains)>=2 or len(names)>=2: ver,lab,detail="CORROBORATED","CORROBORATED","Similar reporting is present across multiple publisher identities in the live feeds."
        elif name!="Unknown publisher": ver,lab,detail="SINGLE_SOURCE","SINGLE SOURCE","Only one publisher currently carries this story cluster in the live feeds."
        else: ver,lab,detail="UNVERIFIED","UNVERIFIED","Publisher could not be established from the feed metadata or headline."
        impact,impact_reason=classify_impact(headline); summary=str(item.get("summary") or ""); article_url=str(item.get("link") or item.get("url") or "")
        agent_status="NOT_RUN"
        if idx<16 and article_url:
            agent=analyze_article(article_url,headline,name); agent_status=agent.get("status","UNKNOWN"); points=agent.get("key_points") or []
            if points: summary=" ".join(p.rstrip(" .")+"." for p in points)
            elif not useful_summary(summary,headline): summary=""
        elif not useful_summary(summary,headline):
            summary=""
        if not summary and idx<16:
            fetched=story_summary(headline,name,article_url)
            if fetched: summary=fetched
        if ver=="CORROBORATED": base_claim="SUPPORTED"; base_detail="The event is supported by multiple publisher identities in the live feeds. This supports the existence of the reported event; individual details still require primary-source confirmation."
        else: base_claim="INSUFFICIENT EVIDENCE"; base_detail="Independent evidence is not yet strong enough for a supported classification."
        out.append({**item,"title":headline,"summary":summary,"publisher":name,"publisher_domain":domain,"cluster_id":cid,"verification":ver,"verification_label":lab,"verification_detail":detail,"impact":impact,"impact_reason":impact_reason,"affected":infer_affected(headline),"checked_at_utc":datetime.now(timezone.utc).isoformat(),"evidence_score":evidence_score(ver,len(names)),"evidence_count":0,"claim_status":base_claim,"claim_status_detail":base_detail,"agent_status":agent_status})
    for item in out[:8]:
        ver,lab,detail,sources,signals=targeted_cross_check(item["title"],item.get("publisher","")); status,status_detail=claim_status(ver,sources,signals)
        item.update({"verification":ver,"verification_label":lab,"verification_detail":detail,"verification_sources":sources,"evidence_score":evidence_score(ver,len(sources)),"evidence_count":len(sources),"claim_status":status,"claim_status_detail":status_detail})
        item["verification_detail"] += f" Claim assessment: {status}. {status_detail} Evidence strength: {item['evidence_score']}/100."
    for item in out:
        status=item.get("claim_status","INSUFFICIENT EVIDENCE"); prefix={"SUPPORTED":"🟢 SUPPORTED","DISPUTED":"🔴 DISPUTED","INSUFFICIENT EVIDENCE":"🟡 INSUFFICIENT EVIDENCE"}.get(status,"🟡 INSUFFICIENT EVIDENCE")
        item["display_title"]=f"{prefix} · {item['title']}"
    return out
