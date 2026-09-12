from datetime import datetime, timezone
import re
from urllib.parse import urlparse

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
    if not domain and name.lower() in known: domain=known[name.lower()]
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
            ver,lab,detail="CORROBORATED","✅ CORROBORATED","Similar reporting found across multiple publisher identities. This is corroboration, not proof that every claim in the story is factually correct."
        elif name!="Unknown publisher":
            ver,lab,detail="SINGLE_SOURCE","⚠️ SINGLE SOURCE","Only one publisher currently carries this story cluster. The claim has not been independently corroborated."
        else:
            ver,lab,detail="UNVERIFIED","⚠️ UNVERIFIED","Publisher could not be established from the feed metadata or headline, so the claim cannot currently be independently assessed."
        impact,impact_reason=classify_impact(headline)
        out.append({**item,"title":headline,"publisher":name,"publisher_domain":domain,"cluster_id":cid,"verification":ver,"verification_label":lab,"verification_detail":detail,"impact":impact,"impact_reason":impact_reason,"affected":infer_affected(headline),"checked_at_utc":datetime.now(timezone.utc).isoformat()})
    return out
