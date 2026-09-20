# 便宜机票 CheapTrip

目标：用户输入出发地和预算，系统自动发现真正便宜的往返旅行机会。

核心规则：
- 每个候选旅行必须同时有去程和返程
- 往返总价 = 去程价格 + 返程价格
- 预算指往返总预算
- 每个目的地只保留最低往返组合
- 最终按往返总价排序
- 不使用猜测价格

V1 暂时通过两个单程查询计算往返总价。后续如果数据源提供完整 round-trip total，则优先使用完整往返报价。

运行：
python -m venv .venv
Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

打开 http://127.0.0.1:8000

API：
POST /api/search

{
  "origin": "沈阳",
  "budget": 500,
  "days_ahead": 30,
  "min_trip_days": 2,
  "max_trip_days": 5,
  "max_destinations": 10,
  "currency": "CNY"
}

当前实现：
- FastAPI
- fast-flights provider
- 主要中国机场城市作为 V1 候选目的地
- 枚举未来日期和旅行天数
- 分别查询去程和返程
- 计算真实往返组合价格
- 对每个目的地保留最低价

下一阶段：
1. 候选目的地粗筛
2. 日期价格缓存
3. 并发查询
4. 重试与限流
5. 历史价格数据库
6. 低价程度计算
7. 微信通知
8. 更完整的机场数据
9. 稳定、合法的商业航班数据源

fast-flights 是第三方 Google Flights 数据抓取项目，不是 Google 官方稳定 API。
