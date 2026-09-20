from app.providers.fast_flights_provider import FastFlightsProvider


def test_extract_min_price_from_explicit_price_fields():
    result = {
        "flights": [
            {"price": "CNY 580"},
            {"price": 430},
            {"duration": 80},
        ]
    }
    assert FastFlightsProvider._extract_min_price(result) == 430


def test_extract_min_price_from_object_attributes():
    class Flight:
        price = 399

    assert FastFlightsProvider._extract_min_price([Flight()]) == 399


def test_extract_min_price_does_not_use_duration_or_timestamp():
    result = {
        "flights": [
            {"duration": 120, "timestamp": 123456789},
        ]
    }
    assert FastFlightsProvider._extract_min_price(result) is None
