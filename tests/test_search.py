from app.core.search import CheapTripSearchService


class FakeProvider:
    def __init__(self):
        self.calls = []

    def one_way_min(self, origin, destination, when):
        from app.core.models import Fare

        self.calls.append((origin, destination, when))
        base = 100 if origin == "SHE" else 80
        return Fare(price=base + when.day, source="fake")


def test_round_trip_is_sum_of_two_legs():
    provider = FakeProvider()
    service = CheapTripSearchService(provider=provider)
    result = service.search(
        origin="沈阳",
        budget=500,
        days_ahead=4,
        min_trip_days=2,
        max_trip_days=2,
        max_destinations=1,
    )
    assert result["results"]
    item = result["results"][0]
    assert item["round_trip_price"] == item["outbound_price"] + item["inbound_price"]


def test_search_caches_same_leg_across_multiple_date_pairs():
    provider = FakeProvider()
    service = CheapTripSearchService(provider=provider)

    service.search(
        origin="沈阳",
        budget=500,
        days_ahead=5,
        min_trip_days=2,
        max_trip_days=4,
        max_destinations=1,
    )

    # With days_ahead=5 and trip lengths 2..4, several date pairs reuse
    # exactly the same one-way leg. The cache means each unique leg/date is
    # requested only once.
    assert len(provider.calls) == len(set(provider.calls))
