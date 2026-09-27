from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.modules.booking.schemas import GuestInfo


class ChannelBookingRequest(BaseModel):
    """A channel pushing a booking into us.

    idempotency_key is mandatory: channels retry, and a replay must return the
    original booking instead of a second one.
    """

    unit_type_id: str
    checkin: dt.date
    checkout: dt.date
    guest: GuestInfo
    idempotency_key: str = Field(min_length=1, max_length=200)


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=2, max_length=120)
