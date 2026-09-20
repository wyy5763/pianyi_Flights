from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from app.core.search import CheapTripSearchService, SearchError

app = FastAPI(title="便宜机票 CheapTrip", version="0.2.0")
service = CheapTripSearchService()


class SearchRequest(BaseModel):
    origin: str = Field(..., min_length=2, max_length=30)
    budget: float | None = Field(default=None, gt=0, le=100000)
    days_ahead: int = Field(default=30, ge=1, le=90)
    min_trip_days: int = Field(default=2, ge=1, le=14)
    max_trip_days: int = Field(default=5, ge=1, le=21)
    max_destinations: int = Field(default=10, ge=1, le=30)
    currency: str = Field(default="CNY", min_length=3, max_length=3)

    @field_validator("origin")
    @classmethod
    def normalize_origin(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("出发地不能为空")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "cheaptrip",
        "version": app.version,
        "date": date.today().isoformat(),
    }


@app.post("/api/search")
def search(req: SearchRequest):
    if req.max_trip_days < req.min_trip_days:
        raise HTTPException(
            status_code=400,
            detail="max_trip_days 必须大于等于 min_trip_days",
        )

    try:
        result = service.search(
            origin=req.origin,
            budget=req.budget,
            days_ahead=req.days_ahead,
            min_trip_days=req.min_trip_days,
            max_trip_days=req.max_trip_days,
            max_destinations=req.max_destinations,
            currency=req.currency,
        )
        if (
            result["search_stats"]["successful_leg_queries"] == 0
            and result["search_stats"]["failed_leg_queries"] > 0
        ):
            raise SearchError("航班数据源暂时无法返回有效价格，请稍后重试。")
        return result
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
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1040px;margin:0 auto;padding:24px;background:#f6f7fb;color:#202124}
.card{background:#fff;border-radius:16px;padding:22px;margin-bottom:16px;box-shadow:0 4px 18px #0000000d}
h1{margin:0 0 8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
label{display:flex;flex-direction:column;gap:6px;font-size:14px;font-weight:600}
input{width:100%;padding:11px;border:1px solid #ddd;border-radius:10px;font-size:15px;background:#fff}
button{margin-top:18px;padding:12px 20px;border:0;border-radius:10px;cursor:pointer;font-size:16px;background:#202124;color:#fff}
button:disabled{opacity:.55;cursor:wait}.result{padding:18px}.route{font-size:18px;font-weight:700}.price{font-size:30px;font-weight:800;margin:6px 0}.muted{color:#6b7280}.error{color:#b42318}
.stats{display:flex;flex-wrap:wrap;gap:8px;font-size:13px;color:#6b7280}.pill{background:#f1f3f4;padding:6px 9px;border-radius:999px}
.empty{text-align:center;padding:32px;color:#6b7280}
</style>
</head>
<body>
<div class="card">
<h1>✈️ 便宜机票</h1>
<p class="muted">不知道去哪？输入出发地和预算，自动寻找真正便宜的往返旅行。</p>
<div class="grid">
<label>出发地<input id="origin" value="沈阳" maxlength="30"></label>
<label>往返预算<input id="budget" type="number" min="1" placeholder="例如 500"></label>
<label>未来搜索天数<input id="ahead" type="number" min="1" max="90" value="30"></label>
<label>最少旅行天数<input id="minDays" type="number" min="1" max="14" value="2"></label>
<label>最多旅行天数<input id="maxDays" type="number" min="1" max="21" value="5"></label>
<label>目的地数量<input id="destinations" type="number" min="1" max="30" value="10"></label>
</div>
<button id="searchBtn" onclick="search()">开始寻找低价旅行</button>
</div>
<div id="status"></div>
<div id="results"></div>
<script>
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));

async function search(){
  const button=$('searchBtn'), status=$('status'), results=$('results');
  const minDays=Number($('minDays').value), maxDays=Number($('maxDays').value);
  if(maxDays < minDays){
    status.innerHTML='<div class="card error">最多旅行天数不能小于最少旅行天数。</div>';
    return;
  }

  button.disabled=true;
  status.innerHTML='<div class="card">正在查询去程和返程价格，请稍候……</div>';
  results.innerHTML='';

  const rawBudget=$('budget').value;
  const body={
    origin:$('origin').value.trim(),
    budget:rawBudget ? Number(rawBudget) : null,
    days_ahead:Number($('ahead').value),
    min_trip_days:minDays,
    max_trip_days:maxDays,
    max_destinations:Number($('destinations').value),
    currency:'CNY'
  };

  try{
    const r=await fetch('/api/search',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail || '搜索失败');

    const stats=data.search_stats || {};
    status.innerHTML='<div class="card">'+
      '<b>搜索完成</b>'+
      '<div class="stats" style="margin-top:10px">'+
      '<span class="pill">目的地 '+stats.destinations_checked+'</span>'+
      '<span class="pill">往返组合 '+stats.candidate_round_trips+'</span>'+
      '<span class="pill">有效航段 '+stats.successful_leg_queries+'</span>'+
      '<span class="pill">失败航段 '+stats.failed_leg_queries+'</span>'+
      '</div></div>';

    if(!data.results.length){
      results.innerHTML='<div class="card empty">'+
        (body.budget ? '当前预算内没有找到完整的往返组合。可以提高预算或扩大搜索天数。' : '当前搜索窗口没有找到完整的往返组合。')+
        '</div>';
      return;
    }

    results.innerHTML=data.results.map((x,i)=>
      '<div class="card result">'+
        '<div class="route">#'+(i+1)+' '+esc(x.origin_name)+' → '+esc(x.destination_name)+'</div>'+
        '<div class="price">¥'+esc(x.round_trip_price)+'</div>'+
        '<div>'+esc(x.departure_date)+' → '+esc(x.return_date)+' · '+esc(x.trip_days)+'天</div>'+
        '<div class="muted" style="margin-top:8px">去程 ¥'+esc(x.outbound_price)+
        ' + 返程 ¥'+esc(x.inbound_price)+' = 往返 ¥'+esc(x.round_trip_price)+
        ' · '+esc(x.price_source)+'</div>'+
      '</div>'
    ).join('');
  }catch(e){
    status.innerHTML='<div class="card error">'+esc(e.message)+'</div>';
  }finally{
    button.disabled=false;
  }
}
</script>
</body>
</html>
"""
