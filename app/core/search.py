from datetime import date, timedelta

from app.core.models import RoundTripDeal
from app.data.airports import destinations_for, resolve_origin
from app.providers.fast_flights_provider import FastFlightsProvider, ProviderError


class SearchError(RuntimeError):
    pass


class CheapTripSearchService:
    def __init__(self, provider=None):
        self.provider = provider or FastFlightsProvider()

    @staticmethod
    def _date_pairs(start: date, days_ahead: int, min_days: int, max_days: int):
        end = start + timedelta(days=days_ahead)
        for offset in range(days_ahead):
            departure = start + timedelta(days=offset)
            for trip_days in range(min_days, max_days + 1):
                return_date = departure + timedelta(days=trip_days)
                if return_date <= end:
                    yield departure, return_date

    def search(
        self,
        origin: str,
        budget: float | None,
        days_ahead: int,
        min_trip_days: int,
        max_trip_days: int,
        max_destinations: int,
        currency: str = "CNY",
    ):
        if currency != "CNY":
            raise SearchError("V1 当前只支持 CNY")
        if max_trip_days < min_trip_days:
            raise SearchError("max_trip_days 必须大于等于 min_trip_days")

        try:
            origin_airport = resolve_origin(origin)
        except ValueError as exc:
            raise SearchError(str(exc)) from exc

        today = date.today()
        deals: list[RoundTripDeal] = []

        for destination in destinations_for(origin_airport, max_destinations):
            best = None

            for departure, return_date in self._date_pairs(
                today, days_ahead, min_trip_days, max_trip_days
            ):
                try:
                    outbound = self.provider.one_way_min(
                        origin_airport.code, destination.code, departure
                    )
                    inbound = self.provider.one_way_min(
                        destination.code, origin_airport.code, return_date
                    )
                except ProviderError:
                    continue

                total = round(outbound.price + inbound.price, 2)
                if budget is not None and total > budget:
                    continue

                deal = RoundTripDeal(
                    origin_code=origin_airport.code,
                    origin_name=origin_airport.city,
                    destination_code=destination.code,
                    destination_name=destination.city,
                    departure_date=departure,
                    return_date=return_date,
                    outbound_price=round(outbound.price, 2),
                    inbound_price=round(inbound.price, 2),
                    round_trip_price=total,
                    currency=currency,
                    price_source="outbound + inbound",
                )
                if best is None or deal.round_trip_price < best.round_trip_price:
                    best = deal

            if best:
                deals.append(best)

        deals.sort(key=lambda item: (item.round_trip_price, item.trip_days, item.departure_date))

        return {
            "origin": origin_airport.code,
            "origin_name": origin_airport.city,
            "budget": budget,
            "currency": currency,
            "search_window_days": days_ahead,
            "trip_days": {"min": min_trip_days, "max": max_trip_days},
            "results": [
                {
                    "origin_code": item.origin_code,
                    "origin_name": item.origin_name,
                    "destination_code": item.destination_code,
                    "destination_name": item.destination_name,
                    "departure_date": item.departure_date.isoformat(),
                    "return_date": item.return_date.isoformat(),
                    "trip_days": item.trip_days,
                    "outbound_price": item.outbound_price,
                    "inbound_price": item.inbound_price,
                    "round_trip_price": item.round_trip_price,
                    "currency": item.currency,
                    "price_source": item.price_source,
                }
                for item in deals
            ],
        }
