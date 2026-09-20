from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Airport:
    city: str
    code: str
    name: str = ""


@dataclass(frozen=True)
class Fare:
    price: float
    currency: str = "CNY"
    source: str = "provider"


@dataclass(frozen=True)
class RoundTripDeal:
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    departure_date: date
    return_date: date
    outbound_price: float
    inbound_price: float
    round_trip_price: float
    currency: str
    price_source: str

    @property
    def trip_days(self) -> int:
        return (self.return_date - self.departure_date).days
