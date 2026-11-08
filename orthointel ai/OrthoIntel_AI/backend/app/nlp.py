import re
from collections import Counter

PILLAR_TERMS = {
    "product_performance": ["support", "compression", "pain", "relief", "stability", "effective", "slip", "weak"],
    "durability": ["durable", "wear", "tear", "tearing", "peeling", "velcro", "stitch", "broken", "wash", "quality", "material", "snap"],
    "cost_vs_value": ["price", "expensive", "cheap", "cost", "value", "worth", "overpriced", "affordable"],
    "ease_of_use_and_fit": ["size", "fit", "tight", "loose", "comfortable", "uncomfortable", "strap", "adjust", "difficult", "easy"]
}
POSITIVE = {"good", "great", "excellent", "comfortable", "effective", "durable", "strong", "easy", "perfect", "supportive", "worth"}
NEGATIVE = {"bad", "poor", "weak", "pain", "uncomfortable", "expensive", "broken", "tear", "tearing", "peeling", "difficult", "loose", "tight", "defective", "disappointed", "waste", "wear", "wears"}
NEGATIONS = {"not", "never", "no", "isn't", "wasn't", "doesn't", "without"}

def analyze_review(text: str):
    words = re.findall(r"[a-zA-Z']+", text.lower())
    normalized = [w.strip("'") for w in words]
    pos = neg = 0
    for i, word in enumerate(normalized):
        negated = any(x in NEGATIONS for x in normalized[max(0, i-2):i])
        if word in POSITIVE:
            neg += 1 if negated else 0
            pos += 0 if negated else 1
        if word in NEGATIVE:
            pos += 1 if negated else 0
            neg += 0 if negated else 1
    total = pos + neg
    score = (pos - neg) / total if total else 0.0
    sentiment = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    pillars = {}
    for pillar, terms in PILLAR_TERMS.items():
        matched = [term for term in terms if any(term in w for w in normalized)]
        pillars[pillar] = {"mentioned": bool(matched), "keywords": matched,
                           "signal": "needs_attention" if pillar == "durability" and any(x in matched for x in ["wear","tear","tearing","peeling","broken","snap"]) else ("mentioned" if matched else "not_mentioned")}
    recs = []
    if pillars["durability"]["mentioned"] and pillars["durability"]["signal"] == "needs_attention":
        recs.append("Inspect material, stitching and repeated-use durability tests.")
    if pillars["ease_of_use_and_fit"]["mentioned"] and any(x in normalized for x in ["size","tight","loose","fit"]):
        recs.append("Review size chart, fit guidance and sample measurements.")
    if pillars["cost_vs_value"]["mentioned"] and any(x in normalized for x in ["expensive","overpriced"]):
        recs.append("Review perceived value, competitor pricing and product-cost structure.")
    if not recs:
        recs.append("Continue monitoring feedback and compare it with sales and returns.")
    return {"sentiment": sentiment, "sentiment_score": round(score, 3), "positive_terms": pos,
            "negative_terms": neg, "pillars": pillars, "recommendations": recs}

def keyword_summary(texts, limit=12):
    stop = {"this","that","with","from","after","have","has","the","and","for","but","was","are","is","it","very","product"}
    tokens = []
    for text in texts:
        tokens.extend(w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in stop)
    return [{"keyword": k, "count": v} for k, v in Counter(tokens).most_common(limit)]
