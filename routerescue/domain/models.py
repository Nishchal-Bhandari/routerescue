from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Constraints(BaseModel):
    cash_limit_minor: int = Field(default=500000, ge=0, le=100000000)
    latest_arrival: datetime
    passengers: int = Field(default=1, ge=1, le=8)
    allowed_modes: list[Literal['bus', 'air', 'train']] = ['bus', 'air', 'train']
    bags: int = Field(default=1, ge=0, le=5)
    wheelchair: bool = False
    preference: Literal['lowest_cost', 'earliest_arrival'] = 'lowest_cost'

    @model_validator(mode='after')
    def timezone_required(self):
        if self.latest_arrival.tzinfo is None:
            raise ValueError('Arrival must include a timezone')
        if not self.allowed_modes:
            raise ValueError('Choose at least one transport mode')
        return self


class TripInput(BaseModel):
    title: str = Field(default='A weekend in Bengaluru', min_length=1, max_length=100)
    scenario: Literal['flight', 'train', 'hotel'] = 'flight'
    origin: Literal['Mangaluru'] = 'Mangaluru'
    destination: Literal['Bengaluru'] = 'Bengaluru'
    travel_date: Literal['2026-11-15'] = '2026-11-15'
    constraints: Constraints = Field(default_factory=lambda: Constraints(latest_arrival='2026-11-15T19:00:00+05:30'))


class EventInput(BaseModel):
    event_type: Literal['FLIGHT_CANCELLED', 'TRAIN_DELAYED', 'HOTEL_CANCELLED', 'BUS_UNAVAILABLE']
    source_event_id: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=2000)
    available_from: datetime | None = None

    @model_validator(mode='after')
    def aware_report_time(self):
        if self.available_from and self.available_from.tzinfo is None:
            raise ValueError('Available-from time must include a timezone')
        return self


class ConstraintPatch(BaseModel):
    expected_version: int = Field(ge=1)
    constraints: Constraints


class ConfirmInput(BaseModel):
    snapshot_hash: str
    idempotency_key: str = Field(min_length=8, max_length=120)


def iso_now():
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None:
        raise ValueError('Offset-aware timestamps required')
    return result
