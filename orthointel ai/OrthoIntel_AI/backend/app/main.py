from pathlib import Path
import csv, io, json, os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .database import init_db, get_db, ROOT
from .models import ReviewInput, CompetitorInput, TicketInput, TicketStatusInput, MarginInput
from .nlp import analyze_review
from .analytics import sales_summary, review_summary, root_cause_analysis

app = FastAPI(title="OrthoIntel AI API", version="1.0.0",
 description="Orthopaedic manufacturer intelligence: reviews, sales, root-cause signals and operational actions.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()
    seed_demo_data()

def audit(action, details="", actor="Admin"):
    with get_db() as db:
        db.execute("INSERT INTO audit_events(actor,action,details) VALUES(?,?,?)",(actor,action,details))

def seed_demo_data():
    with get_db() as db:
        if db.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
            sales = [
             ("2026-08-01","Hyderabad","Knee Support X200",420000,600,18,230000,"Retail"),
             ("2026-09-01","Hyderabad","Knee Support X200",380000,540,25,210000,"Retail"),
             ("2026-08-01","Delhi","Knee Immobilizer",510000,620,20,300000,"Distributor"),
             ("2026-09-01","Delhi","Knee Immobilizer",418000,510,31,260000,"Distributor"),
             ("2026-08-01","Mumbai","Lumbo-Sacral Back Belt",360000,450,14,190000,"Retail"),
             ("2026-09-01","Mumbai","Lumbo-Sacral Back Belt",325000,405,22,175000,"Retail"),
             ("2026-09-01","Chennai","Wrist Support",290000,500,9,145000,"Retail"),
             ("2026-09-01","Bengaluru","Ankle Brace",310000,470,12,160000,"Retail")]
            db.executemany("INSERT INTO sales(date,region,product,sales,units_sold,returns,cost,channel) VALUES(?,?,?,?,?,?,?,?)",sales)
        if db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0:
            samples=[
             ("The knee support is comfortable and gives excellent stability.","Knee Support X200","Hyderabad","Amazon India",5),
             ("The size is too tight and the fit is not correct.","Knee Support X200","Hyderabad","Flipkart",2),
             ("Velcro stitching is tearing after two weeks of use.","Knee Immobilizer","Delhi","Amazon India",1),
             ("The material wears out quickly after washing.","Lumbo-Sacral Back Belt","Mumbai","Retail feedback",2),
             ("Good support but the product feels expensive for this quality.","Wrist Support","Chennai","Amazon India",3),
             ("Easy to adjust and comfortable for daily use.","Ankle Brace","Bengaluru","Retail feedback",5)]
            for review,product,region,source,rating in samples:
                a=analyze_review(review)
                db.execute("INSERT INTO reviews(review,product,region,source,rating,sentiment,sentiment_score,pillars) VALUES(?,?,?,?,?,?,?,?)",
                  (review,product,region,source,rating,a["sentiment"],a["sentiment_score"],json.dumps(a["pillars"])))

@app.get("/")
def home():
    return FileResponse(ROOT/"frontend"/"index.html")


@app.get("/api/templates/sales.csv")
def sales_template():
    return FileResponse(ROOT/"backend"/"data"/"sample_sales.csv", filename="sample_sales.csv", media_type="text/csv")

@app.get("/api/templates/reviews.csv")
def reviews_template():
    return FileResponse(ROOT/"backend"/"data"/"sample_reviews.csv", filename="sample_reviews.csv", media_type="text/csv")
@app.get("/api/health")
def health():
    return {"status":"ok","service":"OrthoIntel AI","database":"connected","version":"1.0.0"}

@app.get("/api/dashboard")
def dashboard():
    s=sales_summary(); r=review_summary()
    return {"sales":s,"reviews":r,"alerts":len(root_cause_analysis()),"system_status":"Operational"}

@app.post("/api/analyze-review")
def analyze_one(payload: ReviewInput):
    result=analyze_review(payload.review)
    with get_db() as db:
        cur=db.execute("""INSERT INTO reviews(review,product,region,source,rating,sentiment,sentiment_score,pillars)
        VALUES(?,?,?,?,?,?,?,?)""",(payload.review,payload.product,payload.region,payload.source,payload.rating,
        result["sentiment"],result["sentiment_score"],json.dumps(result["pillars"])))
        review_id=cur.lastrowid
    audit("review_analyzed",f"review_id={review_id}; product={payload.product}")
    return {"id":review_id,"review":payload.review,**result}

@app.get("/api/reviews")
def get_reviews():
    return review_summary()

@app.post("/api/reviews/upload")
async def upload_reviews(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Please upload a CSV file.")
    raw=(await file.read()).decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "review" not in [x.lower() for x in reader.fieldnames]:
        raise HTTPException(400,"CSV must contain a 'review' column.")
    count=0
    for row in reader:
        row={str(k).lower():v for k,v in row.items()}
        review=(row.get("review") or "").strip()
        if not review: continue
        a=analyze_review(review)
        with get_db() as db:
            db.execute("INSERT INTO reviews(review,product,region,source,rating,sentiment,sentiment_score,pillars) VALUES(?,?,?,?,?,?,?,?)",
             (review,row.get("product") or "Unspecified",row.get("region") or "Unknown",row.get("source") or file.filename,
              float(row["rating"]) if row.get("rating") else None,a["sentiment"],a["sentiment_score"],json.dumps(a["pillars"])))
        count+=1
    audit("reviews_uploaded",f"{count} reviews from {file.filename}")
    return {"imported":count,"summary":review_summary()}

@app.post("/api/sales/upload")
async def upload_sales(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Please upload a CSV file.")
    raw=(await file.read()).decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(raw))
    fields=[x.lower() for x in (reader.fieldnames or [])]
    required={"region","product","sales"}
    if not required.issubset(set(fields)): raise HTTPException(400,"Sales CSV requires columns: region, product, sales.")
    count=0
    for original in reader:
        row={str(k).lower():v for k,v in original.items()}
        try:
            values=(row.get("date") or None,row["region"],row["product"],float(row["sales"]),
                    float(row.get("units_sold") or 0),float(row.get("returns") or 0),
                    float(row.get("cost") or 0),row.get("channel") or "Unknown")
        except (ValueError,KeyError): continue
        with get_db() as db:
            db.execute("INSERT INTO sales(date,region,product,sales,units_sold,returns,cost,channel) VALUES(?,?,?,?,?,?,?,?)",values)
        count+=1
    audit("sales_uploaded",f"{count} sales rows from {file.filename}")
    return {"imported":count,"summary":sales_summary()}

@app.get("/api/sales")
def get_sales(): return sales_summary()

@app.get("/api/root-cause")
def root_cause(): return {"items":root_cause_analysis(),"note":"Signals are associations for human investigation, not causal proof."}

@app.post("/api/competitors")
def add_competitor(payload: CompetitorInput):
    with get_db() as db:
        cur=db.execute("INSERT INTO competitor_observations(competitor,product,region,status) VALUES(?,?,?,?)",
         (payload.competitor,payload.product,payload.region,payload.status))
    audit("competitor_observation_added",f"{payload.competitor}: {payload.status} in {payload.region}")
    return {"id":cur.lastrowid,"message":"Observation saved. Validate the source and timestamp before acting."}

@app.get("/api/competitors")
def get_competitors():
    with get_db() as db:
        rows=[dict(x) for x in db.execute("SELECT * FROM competitor_observations ORDER BY id DESC LIMIT 100")]
    return {"items":rows}

@app.post("/api/margin/calculate")
def calculate_margin(payload: MarginInput):
    retail_net=payload.mrp*(1-payload.retailer_margin_pct/100)
    company_contribution=retail_net-payload.base_cost
    suggested_net=payload.mrp*(1-payload.proposed_trade_margin_pct/100)
    contribution=suggested_net-payload.base_cost
    margin_pct=contribution/suggested_net*100 if suggested_net else 0
    safe=margin_pct >= payload.minimum_company_margin_pct
    max_trade=(1-(payload.base_cost/(payload.mrp*(1-payload.minimum_company_margin_pct/100))))*100
    return {"mrp":payload.mrp,"base_cost":payload.base_cost,"current_net_realization":round(retail_net,2),
      "proposed_net_realization":round(suggested_net,2),"current_contribution":round(company_contribution,2),
      "proposed_contribution":round(contribution,2),"company_margin_pct":round(margin_pct,2),
      "minimum_company_margin_pct":payload.minimum_company_margin_pct,"within_guardrail":safe,
      "maximum_trade_margin_pct":round(max(0,min(80,max_trade)),2),
      "recommendation":"Offer is within the configured margin floor." if safe else "Offer is below the configured company margin floor; revise or seek approval.",
      "note":"Illustrative calculation. Confirm tax, channel terms, schemes, freight, credit costs and the precise margin base before commercial use."}

@app.post("/api/factory/tickets")
def create_ticket(payload: TicketInput):
    with get_db() as db:
        cur=db.execute("INSERT INTO factory_tickets(product,issue,recommendation,priority) VALUES(?,?,?,?)",
         (payload.product,payload.issue,payload.recommendation,payload.priority))
    audit("factory_ticket_created",f"ticket_id={cur.lastrowid}; product={payload.product}")
    return {"id":cur.lastrowid,"status":"Open","message":"Engineering ticket created for human review."}

@app.get("/api/factory/tickets")
def list_tickets():
    with get_db() as db:
        return {"items":[dict(x) for x in db.execute("SELECT * FROM factory_tickets ORDER BY id DESC")]}

@app.patch("/api/factory/tickets/{ticket_id}")
def update_ticket(ticket_id:int,payload:TicketStatusInput):
    with get_db() as db:
        cur=db.execute("UPDATE factory_tickets SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(payload.status,ticket_id))
        if cur.rowcount==0: raise HTTPException(404,"Ticket not found.")
    audit("factory_ticket_status_changed",f"ticket_id={ticket_id}; status={payload.status}")
    return {"id":ticket_id,"status":payload.status}

@app.get("/api/reports/summary.csv")
def export_summary():
    s=sales_summary()
    output=io.StringIO()
    writer=csv.writer(output); writer.writerow(["Region","Product","Sales INR","Units","Returns"])
    for p in s["products"]:
        writer.writerow(["All regions",p["product"],p["sales"],p["units"],p["returns"]])
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
      headers={"Content-Disposition":"attachment; filename=orthointel_sales_summary.csv"})

@app.get("/api/audit")
def audit_log():
    with get_db() as db: rows=[dict(x) for x in db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 100")]
    return {"items":rows}

app.mount("/assets",StaticFiles(directory=ROOT/"frontend"),name="assets")
