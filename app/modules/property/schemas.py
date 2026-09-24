from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PropertyType = Literal["hotel", "apartment", "house", "room", "hostel"]
PropertyStatus = Literal["draft", "pending_moderation", "published", "blocked"]


class PropertyBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    property_type: PropertyType
    city: str = Field(default="", max_length=80)
    timezone: str = Field(default="Europe/Simferopol")  # Crimea: Europe/Simferopol
    checkin_time: dt.time = Field(default=dt.time(14, 0))
    checkout_time: dt.time = Field(default=dt.time(12, 0))
    currency: str = Field(default="RUB", max_length=3)
    lat: float | None = None
    lng: float | None = None
    address: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tz(self) -> PropertyBase:
        from zoneinfo import available_timezones

        if self.timezone not in available_timezones():
            raise ValueError(f"unknown IANA timezone: {self.timezone}")
        return self


class PropertyCreate(PropertyBase):
    """Partner-facing create payload. Status always starts as draft."""


class PropertyUpdate(BaseModel):
    """Partial update. Only the fields the partner is allowed to change."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    timezone: str | None = None
    checkin_time: dt.time | None = None
    checkout_time: dt.time | None = None
    lat: float | None = None
    lng: float | None = None
    address: dict | None = None
    status: PropertyStatus | None = None

    @model_validator(mode="after")
    def validate_tz(self) -> PropertyUpdate:
        if self.timezone is not None:
            from zoneinfo import available_timezones

            if self.timezone not in available_timezones():
                raise ValueError(f"unknown IANA timezone: {self.timezone}")
        return self


class PropertyOut(BaseModel):
    id: str
    partner_id: str
    name: str
    slug: str | None
    property_type: PropertyType
    city: str
    timezone: str
    checkin_time: dt.time
    checkout_time: dt.time
    currency: str
    status: PropertyStatus
    lat: float | None
    lng: float | None
    address: dict
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class PropertyPublicOut(BaseModel):
    """Catalog view — no partner/internal fields."""

    id: str
    name: str
    slug: str | None
    property_type: PropertyType
    city: str
    timezone: str
    checkin_time: dt.time
    checkout_time: dt.time
    currency: str
    lat: float | None
    lng: float | None
    address: dict
