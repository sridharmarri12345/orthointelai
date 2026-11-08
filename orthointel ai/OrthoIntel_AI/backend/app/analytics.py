import pandas as pd
from .database import get_db
from .nlp import analyze_review, keyword_summary
import json

def sales_summary():
    with get_db() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM sales ORDER BY date")]
    if not rows:
        return {"total_sales": 0, "units_sold": 0, "returns": 0, "return_rate": 0, "regions": [], "products": [], "monthly": []}
    df = pd.DataFrame(rows)
    total = float(df["sales"].fillna(0).sum())
    units = float(df["units_sold"].fillna(0).sum())
    returns = float(df["returns"].fillna(0).sum())
    regions = df.groupby("region", as_index=False).agg(sales=("sales","sum"), units=("units_sold","sum")).sort_values("sales", ascending=False)
    products = df.groupby("product", as_index=False).agg(sales=("sales","sum"), units=("units_sold","sum"), returns=("returns","sum")).sort_values("sales", ascending=False)
    monthly = []
    if "date" in df and df["date"].notna().any():
        df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
        monthly = df.dropna(subset=["month"]).groupby("month", as_index=False)["sales"].sum().to_dict("records")
    return {"total_sales": round(total,2), "units_sold": round(units,2), "returns": round(returns,2),
            "return_rate": round(returns / units * 100,2) if units else 0,
            "regions": regions.to_dict("records"), "products": products.to_dict("records"), "monthly": monthly}

def review_summary():
    with get_db() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM reviews ORDER BY id DESC")]
    if not rows:
        return {"count":0,"sentiment":{"positive":0,"neutral":0,"negative":0},"pillars":{},"keywords":[],"reviews":[]}
    sentiments = {k:sum(1 for r in rows if r["sentiment"]==k) for k in ["positive","neutral","negative"]}
    pillars = {}
    for p in ["product_performance","durability","cost_vs_value","ease_of_use_and_fit"]:
        selected = [r for r in rows if json.loads(r["pillars"]).get(p,{}).get("mentioned")]
        pillars[p] = {"mentions":len(selected), "negative":sum(1 for r in selected if r["sentiment"]=="negative")}
    return {"count":len(rows),"sentiment":sentiments,"pillars":pillars,
            "keywords":keyword_summary([r["review"] for r in rows]),
            "reviews":rows[:30]}

def root_cause_analysis():
    with get_db() as db:
        sales = [dict(r) for r in db.execute("SELECT region, product, SUM(sales) sales, SUM(units_sold) units, SUM(returns) returns FROM sales GROUP BY region, product")]
        reviews = [dict(r) for r in db.execute("SELECT product, region, sentiment, pillars, review FROM reviews")]
    result=[]
    # Compare the two latest available monthly sales totals for each product/region.
    trend_map = {}
    if sales:
        with get_db() as db:
            trend_rows = [dict(r) for r in db.execute(
                "SELECT region, product, substr(date,1,7) AS month, SUM(sales) AS amount "
                "FROM sales WHERE date IS NOT NULL AND date <> '' "
                "GROUP BY region, product, substr(date,1,7) ORDER BY month"
            )]
        from collections import defaultdict
        buckets = defaultdict(list)
        for row in trend_rows:
            buckets[(row["region"], row["product"])].append(row)
        for key, rows in buckets.items():
            rows = sorted(rows, key=lambda x: x["month"])
            if len(rows) >= 2 and rows[-2]["amount"]:
                trend_map[key] = round((rows[-1]["amount"] - rows[-2]["amount"]) / rows[-2]["amount"] * 100, 1)
    for s in sales:
        matching=[r for r in reviews if (r["product"].lower() in ["unspecified",s["product"].lower()] or s["product"].lower() in r["product"].lower()) and (r["region"].lower() in ["unknown",s["region"].lower()])]
        if not matching: continue
        negative=[r for r in matching if r["sentiment"]=="negative"]
        pillar_counts={}
        for r in matching:
            data=json.loads(r["pillars"])
            for p,v in data.items():
                if v.get("mentioned"):
                    pillar_counts[p]=pillar_counts.get(p,0)+1
        dominant=max(pillar_counts,key=pillar_counts.get) if pillar_counts else "insufficient_evidence"
        result.append({"region":s["region"],"product":s["product"],"sales":round(s["sales"] or 0,2),
          "units":s["units"] or 0,"returns":s["returns"] or 0,"review_count":len(matching),
          "negative_reviews":len(negative),"negative_share_pct":round(len(negative)/len(matching)*100,1),
          "sales_change_pct":trend_map.get((s["region"], s["product"])),
          "dominant_pillar":dominant,"signal":"Investigate" if negative else "Monitor",
          "interpretation":"Feedback and sales are linked by product/region for investigation; this is an association, not causal proof."})
    return result
