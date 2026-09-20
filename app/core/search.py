from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import time

from app.core.models import Fare, RoundTripDeal
from app.data.airports import destinations_for, resolve_origin
from app.providers.fast_flights_provider import FastFlightsProvider, ProviderError


class SearchError(RuntimeError):
    pass


class CheapTripSearchService:
    def __init__(
        self,
        provider=None,
        max_workers: int = 6,
        max_retries: int = 2,
        retry_delay: float = 0.6,
    ):
        self.provider = provider or FastFlightsProvider()
        self.max_workers = max(1, min(max_workers, 12))
        self.max_retries = max(0, min(max_retries, 5))
        self.retry_delay = max(0.0, retry_delay)

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
        pairs = list(
            CheapTripSearchService._date_pairs(
                start, days_ahead, min_days, max_days
            )
        )
        return (
            sorted({departure for departure, _ in pairs}),
            sorted({return_date for _, return_date in pairs}),
        )

    def _fetch_one(
        self,
        origin: str,
        destination: str,
        when: date,
    ) -> tuple[tuple[str, str, date], Fare | None]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return (
                    (origin, destination, when),
                    self.provider.one_way_min(origin, destination, when),
                )
            except ProviderError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
        return ((origin, destination, when), None)

    def _load_legs(
        self,
        origin_code: str,
        destinations,
        outbound_dates: list[date],
        inbound_dates: list[date],
    ) -> tuple[dict[tuple[str, str, date], Fare], int]:
        keys = {
            (origin_code, destination.code, when)
            for destination in destinations
            for when in outbound_dates
        }
        keys.update(
            {
                (destination.code, origin_code, when)
                for destination in destinations
                for when in inbound_dates
            }
        )

        cache: dict[tuple[str, str, date], Fare] = {}
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._fetch_one, origin, destination, when)
                for origin, destination, when in sorted(keys)
            ]
            for future in as_completed(futures):
                key, fare = future.result()
                if fare is None:
                    failed += 1
                else:
                    cache[key] = fare

        return cache, failed

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
        if days_ahead < 1:
            raise SearchError("days_ahead 必须大于等于 1")
        if max_trip_days < min_trip_days:
            raise SearchError("max_trip_days 必须大于等于 min_trip_days")

        try:
            origin_airport = resolve_origin(origin)
        except ValueError as exc:
            raise SearchError(str(exc)) from exc

        today = date.today()
        destinations = destinations_for(origin_airport, max_destinations)
        if not destinations:
            raise SearchError("没有可搜索的目的地")

        outbound_dates, inbound_dates = self._required_dates(
            today, days_ahead, min_trip_days, max_trip_days
        )
        cache, failed_leg_count = self._load_legs(
            origin_airport.code,
            destinations,
            outbound_dates,
            inbound_dates,
        )

        deals: list[RoundTripDeal] = []
        candidate_pair_count = 0

        for destination in destinations:
            best = None
            for departure, return_date in self._date_pairs(
                today, days_ahead, min_trip_days, max_trip_days
            ):
                candidate_pair_count += 1
                outbound = cache.get(
                    (origin_airport.code, destination.code, departure)
                )
                inbound = cache.get(
                    (destination.code, origin_airport.code, return_date)
                )
                if outbound is None or inbound is None:
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
                if best is None or (
                    deal.round_trip_price,
                    deal.trip_days,
                    deal.departure_date,
                ) < (
                    best.round_trip_price,
                    best.trip_days,
                    best.departure_date,
                ):
                    best = deal

            if best:
                deals.append(best)

        deals.sort(
            key=lambda item: (
                item.round_trip_price,
                item.trip_days,
                item.departure_date,
                item.destination_code,
            )
        )

        return {
            "origin": origin_airport.code,
            "origin_name": origin_airport.city,
            "budget": budget,
            "currency": currency,
            "search_window_days": days_ahead,
            "trip_days": {"min": min_trip_days, "max": max_trip_days},
            "search_stats": {
                "destinations_checked": len(destinations),
                "candidate_round_trips": candidate_pair_count,
                "unique_leg_queries": len(cache) + failed_leg_count,
                "successful_leg_queries": len(cache),
                "failed_leg_queries": failed_leg_count,
                "max_workers": self.max_workers,
            },
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
