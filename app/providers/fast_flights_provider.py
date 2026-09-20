from datetime import date
from typing import Any

from app.core.models import Fare

try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
except ImportError:
    FlightQuery = Passengers = create_query = get_flights = None


class ProviderError(RuntimeError):
    pass


class FastFlightsProvider:
    def __init__(self, language: str = "zh-CN"):
        self.language = language

    def _query(self, origin: str, destination: str, when: date) -> Any:
        if get_flights is None:
            raise ProviderError("未安装 fast-flights，请先安装 requirements.txt")

        flight = FlightQuery(
            date=when.isoformat(),
            from_airport=origin,
            to_airport=destination,
        )
        query = create_query(
            flights=[flight],
            seat="economy",
            trip="one-way",
            passengers=Passengers(adults=1),
            language=self.language,
            currency="CNY",
        )
        try:
            return get_flights(query)
        except Exception as exc:
            raise ProviderError(f"航班数据源请求失败：{exc}") from exc

    @staticmethod
    def _extract_min_price(result: Any) -> float | None:
        prices: list[float] = []
        items = result if isinstance(result, (list, tuple)) else [result]

        for item in items:
            value = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
            if isinstance(value, (int, float)) and value > 0:
                prices.append(float(value))

        return min(prices) if prices else None

    def one_way_min(self, origin: str, destination: str, when: date) -> Fare:
        result = self._query(origin, destination, when)
        price = self._extract_min_price(result)
        if price is None:
            raise ProviderError(
                f"未能解析 {origin}->{destination} {when} 的价格；不会使用猜测价格。"
            )
        return Fare(price=price, currency="CNY", source="fast-flights")
