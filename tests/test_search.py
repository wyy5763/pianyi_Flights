from app.core.search import CheapTripSearchService


class FakeProvider:
    def one_way_min(self, origin, destination, when):
        from app.core.models import Fare
        base = 100 if origin == "SHE" else 80
        return Fare(price=base + when.day, source="fake")


def test_round_trip_is_sum_of_two_legs():
    service = CheapTripSearchService(provider=FakeProvider())
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
