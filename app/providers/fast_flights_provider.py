from datetime import date
import math
import re
from typing import Any

from app.core.models import Fare

try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
except ImportError:
    FlightQuery = Passengers = create_query = get_flights = None


class ProviderError(RuntimeError):
    pass


class FastFlightsProvider:
    def __init__(self, language: str = "zh-CN", currency: str = "CNY"):
        self.language = language
        self.currency = currency

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
            currency=self.currency,
        )
        try:
            return get_flights(query)
        except Exception as exc:
            raise ProviderError(f"航班数据源请求失败：{exc}") from exc

    @staticmethod
    def _to_price(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = float(value)
        elif isinstance(value, str):
            cleaned = re.sub(r"[^0-9.]", "", value.replace(",", ""))
            if not cleaned:
                return None
            try:
                number = float(cleaned)
            except ValueError:
                return None
        else:
            return None

        if not math.isfinite(number) or number <= 0:
            return None
        return number

    @classmethod
    def _extract_min_price(cls, result: Any) -> float | None:
        """
        Extract only explicitly named fare fields.

        fast-flights has changed its parsed result structures across releases,
        so support both object and mapping forms. We deliberately do not scan
        arbitrary numeric fields: durations, timestamps, carbon values, etc.
        are not prices.
        """
        prices: list[float] = []
        visited: set[int] = set()

        def walk(value: Any, depth: int = 0) -> None:
            if value is None or depth > 5:
                return
            identity = id(value)
            if identity in visited:
                return
            visited.add(identity)

            if isinstance(value, dict):
                for key in ("price", "total_price", "amount"):
                    if key in value:
                        price = cls._to_price(value[key])
                        if price is not None:
                            prices.append(price)
                for key in (
                    "flights",
                    "cheaper_alternatives",
                    "booking_options",
                    "results",
                ):
                    if key in value:
                        walk(value[key], depth + 1)
                return

            for attr in ("price", "total_price", "amount"):
                try:
                    raw = getattr(value, attr, None)
                except Exception:
                    raw = None
                price = cls._to_price(raw)
                if price is not None:
                    prices.append(price)

            for attr in (
                "flights",
                "cheaper_alternatives",
                "booking_options",
                "results",
            ):
                try:
                    nested = getattr(value, attr, None)
                except Exception:
                    nested = None
                if nested is not None:
                    walk(nested, depth + 1)

            if isinstance(value, (list, tuple)):
                for item in value:
                    walk(item, depth + 1)

        walk(result)
        return min(prices) if prices else None

    def one_way_min(self, origin: str, destination: str, when: date) -> Fare:
        result = self._query(origin, destination, when)
        price = self._extract_min_price(result)
        if price is None:
            raise ProviderError(
                f"未能解析 {origin}->{destination} {when} 的明确票价；不会使用猜测价格。"
            )
        return Fare(price=price, currency=self.currency, source="fast-flights")
