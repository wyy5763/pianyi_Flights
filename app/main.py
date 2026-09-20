from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.core.search import CheapTripSearchService, SearchError

app = FastAPI(title="便宜机票 CheapTrip", version="0.1.0")
service = CheapTripSearchService()


class SearchRequest(BaseModel):
    origin: str = Field(..., min_length=2)
    budget: float | None = Field(default=None, gt=0)
    days_ahead: int = Field(default=30, ge=1, le=90)
    min_trip_days: int = Field(default=2, ge=1, le=14)
    max_trip_days: int = Field(default=5, ge=1, le=21)
    max_destinations: int = Field(default=10, ge=1, le=50)
    currency: str = Field(default="CNY", min_length=3, max_length=3)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "cheaptrip", "date": date.today().isoformat()}


@app.post("/api/search")
def search(req: SearchRequest):
    if req.max_trip_days < req.min_trip_days:
        raise HTTPException(status_code=400, detail="max_trip_days 必须大于等于 min_trip_days")
    try:
        return service.search(
            origin=req.origin,
            budget=req.budget,
            days_ahead=req.days_ahead,
            min_trip_days=req.min_trip_days,
            max_trip_days=req.max_trip_days,
            max_destinations=req.max_destinations,
            currency=req.currency,
        )
    except SearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)


INDEX_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>便宜机票 CheapTrip</title>
<style>
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:980px;margin:0 auto;padding:28px;background:#f6f7fb;color:#202124}
.card{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 18px #0000000d}
h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
label{display:flex;flex-direction:column;gap:6px;font-size:14px}
input{padding:11px;border:1px solid #ddd;border-radius:10px;font-size:15px}
button{margin-top:18px;padding:12px 18px;border:0;border-radius:10px;cursor:pointer;font-size:16px}
.result{border-top:1px solid #eee;padding:16px 0}.price{font-size:26px;font-weight:700}.muted{color:#6b7280}.error{color:#b42318}
</style>
</head>
<body>
<div class="card">
<h1>✈️ 便宜机票</h1>
<p class="muted">不知道去哪？输入出发地和预算，寻找真正便宜的往返旅行。</p>
<div class="grid">
<label>出发地<input id="origin" value="沈阳"></label>
<label>往返预算<input id="budget" type="number" value="500"></label>
<label>未来搜索天数<input id="ahead" type="number" value="30"></label>
<label>最少旅行天数<input id="minDays" type="number" value="2"></label>
<label>最多旅行天数<input id="maxDays" type="number" value="5"></label>
</div>
<button onclick="search()">开始寻找低价旅行</button>
</div>
<div id="status"></div>
<div id="results"></div>
<script>
async function search(){
  var status=document.getElementById('status');
  var results=document.getElementById('results');
  status.innerHTML='<div class="card">正在搜索往返组合……</div>';
  results.innerHTML='';
  var body={
    origin:document.getElementById('origin').value,
    budget:Number(document.getElementById('budget').value)||null,
    days_ahead:Number(document.getElementById('ahead').value),
    min_trip_days:Number(document.getElementById('minDays').value),
    max_trip_days:Number(document.getElementById('maxDays').value)
  };
  try{
    var r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var data=await r.json();
    if(!r.ok) throw new Error(data.detail||'搜索失败');
    status.innerHTML='<div class="card"><b>搜索完成</b> · '+data.results.length+' 个低价旅行机会</div>';
    results.innerHTML=data.results.map(function(x){
      return '<div class="card result">'+
        '<div><b>'+x.origin_name+'</b> → <b>'+x.destination_name+'</b></div>'+
        '<div class="price">¥'+x.round_trip_price+'</div>'+
        '<div>'+x.departure_date+' → '+x.return_date+' · '+x.trip_days+'天</div>'+
        '<div class="muted">去程 ¥'+x.outbound_price+' + 返程 ¥'+x.inbound_price+' · '+x.price_source+'</div>'+
        '</div>';
    }).join('');
  }catch(e){
    status.innerHTML='<div class="card error">'+e.message+'</div>';
  }
}
</script>
</body>
</html>
"""
