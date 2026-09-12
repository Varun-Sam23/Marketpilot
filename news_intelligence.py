from datetime import datetime, timezone
import re
from urllib.parse import urlparse, quote_plus
import feedparser

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
    explicit=str(item.get("publisher") or "").strip()
    source=item.get("source")
    source_name=""
    if isinstance(source,dict): source_name=str(source.get("title") or source.get("name") or "").strip()
    elif source and not str(source).lower().endswith("markets"): source_name=str(source).strip()
    name=explicit or source_name or title_pub or "Unknown publisher"
    if name.lower()=="news.google.com": name=title_pub or "Unknown publisher"
    domain=""
    known={"reuters":"reuters.com","business standard":"business-standard.com","businessstandard":"business-standard.com","economic times":"economictimes.indiatimes.com","livemint":"livemint.com","moneycontrol":"moneycontrol.com","ndtv profit":"ndtvprofit.com","cnbc tv18":"cnbctv18.com","financial express":"financialexpress.com","hindustan times":"hindustantimes.com"}
    if name.lower() in known: domain=known[name.lower()]
    return headline,name,domain

def words(text):
    return set(re.sub(r"[^a-z0-9 ]"," ",(text or "").lower()).split())

def similarity(a,b):
    wa,wb=words(a),words(b)
    return len(wa&wb)/max(1,len(wa|wb)) if wa and wb else 0

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
    """Conservative evidence score: measures corroboration strength, not probability that a claim is true."""
    if verification=="CONFLICTING": return 35
    if verification=="CROSS_CHECKED": return min(90, 55 + max(0, source_count-2)*10)
    if verification=="CORROBORATED": return min(75, 45 + max(0, source_count-1)*10)
    if verification=="SINGLE_SOURCE": return 30
    return 10

def targeted_cross_check(headline, current_publisher=""):
    """Use a fresh Google News query to look for independent reporting and contradictions.
    This is an evidence cross-check, not a claim of truth. Fail closed when the web feed is unavailable.
    """
    try:
        query=quote_plus('"' + headline[:180] + '"')
        url=f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        feed=feedparser.parse(url)
        sources=[]; impacts=[]
        for entry in feed.entries[:8]:
            title,name=publisher_from_title(entry.get("title", ""))
            src=entry.get("source")
            if isinstance(src,dict): name=str(src.get("title") or src.get("name") or name).strip()
            if not name or name.lower()=="news.google.com": continue
            if current_publisher and name.lower()==current_publisher.lower(): continue
            if any(name.lower()==s.lower() for s in sources): continue
            sources.append(name)
            impacts.append(classify_impact(title)[0])
        if len(sources)>=2:
            pos=impacts.count("POSITIVE"); neg=impacts.count("NEGATIVE")
            if pos and neg and abs(pos-neg)<=1:
                return "CONFLICTING","CONFLICTING REPORTS",f"Fresh search found {len(sources)} independent publishers, but their headline signals conflict. Manual review is required.",sources
            return "CROSS_CHECKED","CROSS-CHECKED",f"Fresh search found independent reporting from {len(sources)} additional publishers. This supports the existence of the reported event but does not prove every detail.",sources
        if len(sources)==1:
            return "SINGLE_SOURCE","SINGLE SOURCE","Only one additional publisher was found in the targeted search. Independent confirmation remains limited.",sources
    except Exception:
        pass
    return "UNVERIFIED","UNVERIFIED","Fresh independent cross-check was unavailable. MarketPilot will not label the claim as verified.",[]

def enrich_news(items):
    if not items: return []
    clusters=cluster_headlines(items); belong={i:(cid,c) for cid,c in enumerate(clusters,1) for i in c}; out=[]
    for idx,item in enumerate(items):
        headline,name,domain=publisher_identity(item); cid,cluster=belong[idx]; domains=set(); names=set()
        for j in cluster:
            _,n,d=publisher_identity(items[j])
            if d: domains.add(d)
            if n and n!="Unknown publisher": names.add(n)
        if len(domains)>=2 or len(names)>=2:
            ver,lab,detail="CORROBORATED","CORROBORATED","Similar reporting is already present across multiple publisher identities in the live feeds. This is corroboration, not proof of factual accuracy."
        elif name!="Unknown publisher":
            ver,lab,detail="SINGLE_SOURCE","SINGLE SOURCE","Only one publisher currently carries this story cluster in the live feeds."
        else:
            ver,lab,detail="UNVERIFIED","UNVERIFIED","Publisher could not be established from the feed metadata or headline."
        impact,impact_reason=classify_impact(headline)
        out.append({**item,"title":headline,"publisher":name,"publisher_domain":domain,"cluster_id":cid,"verification":ver,"verification_label":lab,"verification_detail":detail,"impact":impact,"impact_reason":impact_reason,"affected":infer_affected(headline),"checked_at_utc":datetime.now(timezone.utc).isoformat(),"evidence_score":evidence_score(ver,len(names))})
    # Targeted cross-check only the first few live headlines to keep refreshes fast and fail closed.
    for item in out[:8]:
        ver,lab,detail,sources=targeted_cross_check(item["title"],item.get("publisher",""))
        item["verification"] = ver
        item["verification_label"] = lab
        item["verification_detail"] = detail
        item["verification_sources"] = sources
        item["evidence_score"] = evidence_score(ver,len(sources))
        item["evidence_count"] = len(sources)
        if sources:
            item["verification_detail"] += f" Evidence strength: {item['evidence_score']}/100."
    return out
