from datetime import date, timedelta

from app.core.models import Fare, RoundTripDeal
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

    @staticmethod
    def _required_dates(
        start: date, days_ahead: int, min_days: int, max_days: int
    ) -> tuple[list[date], list[date]]:
        """
        Return the unique outbound and inbound dates needed by all valid pairs.

        This is the main V1 performance optimization: a flight leg such as
        SHE->PEK on a given day can participate in several different return
        combinations, so it must only be fetched once per search.
        """
        pairs = list(
            CheapTripSearchService._date_pairs(
                start, days_ahead, min_days, max_days
            )
        )
        outbound_dates = sorted({departure for departure, _ in pairs})
        inbound_dates = sorted({return_date for _, return_date in pairs})
        return outbound_dates, inbound_dates

    def _get_one_way(
        self,
        cache: dict[tuple[str, str, date], Fare],
        origin: str,
        destination: str,
        when: date,
    ) -> Fare:
        key = (origin, destination, when)
        if key not in cache:
            cache[key] = self.provider.one_way_min(origin, destination, when)
        return cache[key]

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
        cache: dict[tuple[str, str, date], Fare] = {}

        outbound_dates, inbound_dates = self._required_dates(
            today, days_ahead, min_trip_days, max_trip_days
        )

        for destination in destinations_for(origin_airport, max_destinations):
            # Fetch each unique flight leg once, then combine cached fares
            # locally across all valid departure/return date pairs.
            for departure in outbound_dates:
                try:
                    self._get_one_way(
                        cache,
                        origin_airport.code,
                        destination.code,
                        departure,
                    )
                except ProviderError:
                    continue

            for return_date in inbound_dates:
                try:
                    self._get_one_way(
                        cache,
                        destination.code,
                        origin_airport.code,
                        return_date,
                    )
                except ProviderError:
                    continue

            best = None
            for departure, return_date in self._date_pairs(
                today, days_ahead, min_trip_days, max_trip_days
            ):
                try:
                    outbound = cache[
                        (origin_airport.code, destination.code, departure)
                    ]
                    inbound = cache[
                        (destination.code, origin_airport.code, return_date)
                    ]
                except KeyError:
                    # A provider failure for either leg makes this combination
                    # unavailable; never invent or estimate a fare.
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

        deals.sort(
            key=lambda item: (
                item.round_trip_price,
                item.trip_days,
                item.departure_date,
            )
        )

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
