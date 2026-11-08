const API = "";
const $ = (id) => document.getElementById(id);
let regionChart, sentimentChart;
const pillarNames = {
 product_performance:"Product performance", durability:"Durability",
 cost_vs_value:"Cost vs value", ease_of_use_and_fit:"Ease of use & fit"
};
const money = n => "₹" + Number(n||0).toLocaleString("en-IN",{maximumFractionDigits:0});
const num = n => Number(n||0).toLocaleString("en-IN",{maximumFractionDigits:1});
function toast(msg){const t=$("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2800)}
async function api(path, options={}) {
 const res=await fetch(API+path,options);
 const data=await res.json().catch(()=>({detail:"Unexpected server response"}));
 if(!res.ok) throw new Error(data.detail||"Request failed");
 return data;
}
function nav(view){
 document.querySelectorAll(".nav-link").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
 document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id==="view-"+view));
 const label=document.querySelector(`[data-view="${view}"]`)?.textContent.trim()||view;
 $("pageTitle").textContent=label;
 $("sidebar").classList.remove("open");
 if(view==="sales")loadSales(); if(view==="reviews")loadReviews(); if(view==="rootcause")loadRoot();
 if(view==="factory")loadTickets(); if(view==="field")loadField(); if(view==="reports")loadAudit();
}
document.querySelectorAll(".nav-link").forEach(b=>b.addEventListener("click",()=>nav(b.dataset.view)));
document.querySelectorAll("[data-goto]").forEach(b=>b.addEventListener("click",()=>nav(b.dataset.goto)));
$("mobileToggle").addEventListener("click",()=>$("sidebar").classList.toggle("open"));
$("refreshBtn").addEventListener("click",loadDashboard);
$("runAnalysis").addEventListener("click",async()=>{await loadDashboard();await loadRoot();toast("Analysis refreshed from current database.")});
async function loadDashboard(){
 try{
  const d=await api("/api/dashboard"); const s=d.sales,r=d.reviews;
  $("apiStatus").textContent="Connected · v1.0.0";
  $("kpiSales").textContent=money(s.total_sales);$("kpiUnits").textContent=num(s.units_sold);
  $("kpiReviews").textContent=num(r.count);$("kpiReturns").textContent=num(s.return_rate)+"%";
  $("lastUpdated").textContent="Updated "+new Date().toLocaleTimeString();
  $("salesTotal").textContent=money(s.total_sales);$("salesUnits").textContent=num(s.units_sold);
  $("salesReturns").textContent=num(s.returns);$("salesRate").textContent=num(s.return_rate)+"%";
  drawCharts(s,r); renderPillars(r.pillars,"pillarOverview"); renderAlerts(await api("/api/root-cause"));
 }catch(e){$("apiStatus").textContent="Connection error";toast(e.message)}
}
function drawCharts(s,r){
 const labels=s.regions.map(x=>x.region), vals=s.regions.map(x=>x.sales);
 if(regionChart)regionChart.destroy();
 regionChart=new Chart($("regionChart"),{type:"bar",data:{labels,datasets:[{data:vals,label:"Sales (₹)",backgroundColor:"#4b82e8",borderRadius:6,maxBarThickness:30}]},options:{plugins:{legend:{display:false}},scales:{x:{grid:{display:false}},y:{grid:{color:"#edf0f5"},ticks:{callback:v=>"₹"+(v/1000)+"k"}}}}});
 const sentiment=r.sentiment;
 if(sentimentChart)sentimentChart.destroy();
 sentimentChart=new Chart($("sentimentChart"),{type:"doughnut",data:{labels:["Positive","Neutral","Negative"],datasets:[{data:[sentiment.positive,sentiment.neutral,sentiment.negative],backgroundColor:["#32ae91","#e8b45b","#e36c79"],borderWidth:0,hoverOffset:5}]},options:{cutout:"70%",plugins:{legend:{display:false}}}});
 $("sentimentLegend").innerHTML=[["Positive",sentiment.positive,"#32ae91"],["Neutral",sentiment.neutral,"#e8b45b"],["Negative",sentiment.negative,"#e36c79"]].map(x=>`<span style="--dot:${x[2]}">${x[0]} ${x[1]}</span>`).join("");
}
function renderPillars(p,target){
 $(target).innerHTML=Object.entries(p).map(([k,v])=>{const pct=v.mentions?Math.round((v.mentions/Math.max(1,Number($("kpiReviews").textContent.replaceAll(",",""))))*100):0;return `<div class="pillar-row"><span>${pillarNames[k]}</span><div class="bar"><i style="width:${Math.min(100,pct)}%"></i></div><b>${v.mentions} mentions</b></div>`}).join("")||"No pillar data yet.";
}
function renderAlerts(data){
 const items=data.items||[];
 $("dashboardAlerts").innerHTML=items.length?items.slice(0,4).map(x=>`<div class="alert-row"><b>${esc(x.product)} · ${esc(x.region)}</b><p>${esc(pillarNames[x.dominant_pillar]||"Feedback signal")} · ${x.negative_share_pct}% negative among matched reviews</p><span class="status">${esc(x.signal)}</span></div>`).join(""):`<div class="empty-state">No matched review/sales signals. Import reviews with matching product and region names.</div>`;
}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function loadSales(){
 const s=await api("/api/sales");
 $("salesTotal").textContent=money(s.total_sales);$("salesUnits").textContent=num(s.units_sold);$("salesReturns").textContent=num(s.returns);$("salesRate").textContent=num(s.return_rate)+"%";
 $("salesTable").innerHTML=s.products.map(p=>`<tr><td>All regions</td><td>${esc(p.product)}</td><td>${money(p.sales)}</td><td>${num(p.units)}</td><td>${num(p.returns)}</td></tr>`).join("")||'<tr><td colspan="5">No sales data.</td></tr>';
}
async function uploadCsv(input,path){
 const file=input.files[0];if(!file)return;
 const fd=new FormData();fd.append("file",file);
 try{const d=await api(path,{method:"POST",body:fd});toast(`Imported ${d.imported} rows successfully.`);input.value="";await loadDashboard();if(path.includes("sales"))loadSales();else loadReviews()}catch(e){toast(e.message)}
}
$("salesUpload").addEventListener("change",e=>uploadCsv(e.target,"/api/sales/upload"));
$("reviewUpload").addEventListener("change",e=>uploadCsv(e.target,"/api/reviews/upload"));
async function loadReviews(){
 const d=await api("/api/reviews"); const total=d.count||1;
 $("reviewSentiment").innerHTML=Object.entries(d.sentiment).map(([k,v])=>`<div class="sentiment-chip">${k}<b>${v} <small>(${Math.round(v/total*100)}%)</small></b></div>`).join("");
 $("keywords").innerHTML=d.keywords.map(x=>`<span class="keyword">${esc(x.keyword)} · ${x.count}</span>`).join("")||"No keywords";
 $("pillarCards").innerHTML=Object.entries(d.pillars).map(([k,v])=>`<div class="pillar-card"><b>${pillarNames[k]}</b><strong>${v.mentions}</strong><small>${v.negative} negative reviews among mentions</small></div>`).join("");
 $("reviewTable").innerHTML=d.reviews.map(r=>`<tr><td>${esc(r.review.slice(0,100))}${r.review.length>100?"…":""}</td><td>${esc(r.product)}</td><td>${esc(r.region)}</td><td><span class="status">${esc(r.sentiment)}</span></td></tr>`).join("");
}
$("reviewForm").addEventListener("submit",async e=>{
 e.preventDefault();try{
 const d=await api("/api/analyze-review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({review:$("reviewText").value,product:$("reviewProduct").value,region:$("reviewRegion").value,source:$("reviewSource").value,rating:$("reviewRating").value?Number($("reviewRating").value):null})});
 $("singleResult").innerHTML=`<div class="result-box"><h4>Analysis result · ${esc(d.sentiment.toUpperCase())}</h4><p>Sentiment score: ${d.sentiment_score}</p><b>Four pillars</b><ul>${Object.entries(d.pillars).map(([k,v])=>`<li>${pillarNames[k]}: ${v.mentioned?esc(v.signal)+" ("+esc(v.keywords.join(", "))+")":"Not mentioned"}</li>`).join("")}</ul><b>Recommendations</b><ul>${d.recommendations.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div>`;
 $("reviewText").value="";await loadReviews();await loadDashboard();toast("Review analyzed and saved.")
 }catch(err){toast(err.message)}
});
async function loadRoot(){
 const d=await api("/api/root-cause");const items=d.items||[];
 $("rootCards").innerHTML=items.length?items.map(x=>`<article class="root-card"><h3>${esc(x.product)} · ${esc(x.region)}</h3><div class="root-meta">Matched product/region reviews · ${x.review_count} records · <span class="status">${esc(x.signal)}</span></div><div class="root-metrics"><div><b>${money(x.sales)}</b><small>Sales revenue</small></div><div><b>${x.negative_share_pct}%</b><small>Negative review share</small></div><div><b>${x.sales_change_pct===null||x.sales_change_pct===undefined?"—":x.sales_change_pct+"%"}</b><small>Latest monthly sales change</small></div><div><b>${x.returns}<small>Recorded returns</small></div><div><b>${esc(pillarNames[x.dominant_pillar]||"—")}</b><small>Most mentioned pillar</small></div></div><p>${esc(x.interpretation)}</p><button class="text-btn create-ticket" data-product="${esc(x.product)}" data-issue="${esc("Review/sales signal: "+(pillarNames[x.dominant_pillar]||"feedback issue")+" in "+x.region)}">Create factory investigation ticket →</button></article>`).join(""):'<div class="panel empty-state">No matched records. Import sales and reviews with matching product and region values.</div>';
 document.querySelectorAll(".create-ticket").forEach(b=>b.addEventListener("click",()=>{$("ticketProduct").value=b.dataset.product;$("ticketIssue").value=b.dataset.issue;$("ticketRecommendation").value="Validate complaint trend, inspect affected samples/batches and compare with quality-test records.";nav("factory")}));
}
$("refreshRoot").addEventListener("click",()=>loadRoot().then(()=>toast("Root-cause signals recalculated.")));
$("ticketForm").addEventListener("submit",async e=>{
 e.preventDefault();try{await api("/api/factory/tickets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product:$("ticketProduct").value,issue:$("ticketIssue").value,recommendation:$("ticketRecommendation").value,priority:$("ticketPriority").value})});e.target.reset();toast("Engineering ticket created.");loadTickets()}catch(err){toast(err.message)}
});
async function loadTickets(){
 const d=await api("/api/factory/tickets");
 $("ticketTable").innerHTML=d.items.map(t=>`<tr><td>#${t.id}</td><td><b>${esc(t.product)}</b><br>${esc(t.issue.slice(0,75))}</td><td>${esc(t.priority)}</td><td>${esc(t.status)}</td><td><select class="action-select ticket-status" data-id="${t.id}">${["Open","Under Review","Approved","In Progress","Resolved","Rejected"].map(s=>`<option ${s===t.status?"selected":""}>${s}</option>`).join("")}</select></td></tr>`).join("")||'<tr><td colspan="5">No tickets created.</td></tr>';
 document.querySelectorAll(".ticket-status").forEach(s=>s.addEventListener("change",async()=>{try{await api(`/api/factory/tickets/${s.dataset.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:s.value})});toast("Ticket status updated.");}catch(e){toast(e.message)}}));
}
$("competitorForm").addEventListener("submit",async e=>{
 e.preventDefault();try{await api("/api/competitors",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({competitor:$("competitorName").value,product:$("competitorProduct").value,region:$("competitorRegion").value,status:$("competitorStatus").value})});toast("Competitor observation saved.");loadField()}catch(err){toast(err.message)}
});
async function loadField(){
 const d=await api("/api/competitors");
 const demo=[["Central Surgical & Pharma","Connaught Place, Delhi","Potential orthopaedic retail lead"],["Metro Medical Store","Karol Bagh, Delhi","Potential orthopaedic retail lead"],["City Surgical House","Lajpat Nagar, Delhi","Potential orthopaedic retail lead"]];
 $("fieldLeads").innerHTML=demo.map(x=>`<div class="lead"><b>${x[0]}</b><p>${x[1]}<br>${x[2]}</p><a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(x[0]+" "+x[1])}">Open map search ↗</a></div>`).join("");
 $("competitorTable").innerHTML=d.items.map(x=>`<tr><td>${esc(x.competitor)}</td><td>${esc(x.product)}</td><td>${esc(x.region)}</td><td>${esc(x.status)}</td><td>${esc(x.observed_at)}</td></tr>`).join("")||'<tr><td colspan="5">No observations yet.</td></tr>';
}
$("marginForm").addEventListener("submit",async e=>{
 e.preventDefault();try{
 const d=await api("/api/margin/calculate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mrp:Number($("mrp").value),base_cost:Number($("baseCost").value),retailer_margin_pct:Number($("retailerMargin").value),proposed_trade_margin_pct:Number($("proposedMargin").value),minimum_company_margin_pct:Number($("minimumMargin").value)})});
 $("marginResult").innerHTML=`<span class="tag">${d.within_guardrail?"WITHIN GUARDRAIL":"APPROVAL REQUIRED"}</span><h3 style="margin-top:15px">${d.recommendation}</h3><div class="root-metrics"><div><b>${money(d.proposed_net_realization)}</b><small>Company realization</small></div><div><b>${money(d.proposed_contribution)}</b><small>Contribution per unit</small></div><div><b>${d.company_margin_pct}%</b><small>Company contribution margin</small></div><div><b>${d.maximum_trade_margin_pct}%</b><small>Maximum margin at floor</small></div></div><p>${esc(d.note)}</p>`;
 }catch(err){toast(err.message)}
});
async function loadAudit(){
 const d=await api("/api/audit");
 $("auditTable").innerHTML=d.items.map(x=>`<tr><td>${esc(x.created_at)}</td><td>${esc(x.actor)}</td><td>${esc(x.action)}</td><td>${esc(x.details)}</td></tr>`).join("")||'<tr><td colspan="4">No events.</td></tr>';
}
$("refreshAudit").addEventListener("click",loadAudit);
$("footerYear").textContent=new Date().getFullYear();
loadDashboard().catch(()=>{});
