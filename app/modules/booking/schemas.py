from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

BookingStatus = Literal[
    "hold", "paid", "confirmed", "cancelled", "failed", "conflict", "no_show", "refunded"
]


class GuestInfo(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=32)


class HoldRequest(BaseModel):
    unit_type_id: str
    checkin: dt.date
    checkout: dt.date
    guest: GuestInfo


class BookingLineOut(BaseModel):
    date: dt.date
    price: float


class BookingOut(BaseModel):
    id: str
    code: str
    status: BookingStatus
    total_amount: float
    hold_expires_at: dt.datetime | None = None
    checkin_date: dt.date
    checkout_date: dt.date
    lines: list[BookingLineOut] = []


class HoldConflict(BaseModel):
    detail: str
    reason: Literal["not_available", "conflict"] = "not_available"
