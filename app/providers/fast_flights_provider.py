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
    """fast-flights adapter. Provider-specific parsing is isolated here."""

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
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).replace(",", "").replace("¥", "").replace("CNY", "").strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _extract_min_price(self, result: Any) -> float | None:
        candidates: list[float] = []

        def walk(obj: Any, depth: int = 0):
            if depth > 6 or len(candidates) >= 50:
                return
            if isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = str(key).lower()
                    if any(token in key_lower for token in ("price", "fare", "amount", "total")):
                        number = self._number(value)
                        if number is not None and 1 <= number <= 200000:
                            candidates.append(number)
                    walk(value, depth + 1)
            elif isinstance(obj, (list, tuple)):
                for item in obj[:100]:
                    walk(item, depth + 1)
            elif hasattr(obj, "__dict__"):
                walk(vars(obj), depth + 1)

        walk(result)
        return min(candidates) if candidates else None

    def one_way_min(self, origin: str, destination: str, when: date) -> Fare:
        result = self._query(origin, destination, when)
        price = self._extract_min_price(result)
        if price is None:
            raise ProviderError(
                f"未能解析 {origin}->{destination} {when} 的价格；不会使用猜测价格。"
            )
        return Fare(price=price, currency="CNY", source="fast-flights")
