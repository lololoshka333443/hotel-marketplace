from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

PropertyModerationStatus = Literal["draft", "pending_moderation", "published", "blocked"]


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class ModerationRequest(BaseModel):
    """Admin status transition for a property."""

    status: PropertyModerationStatus


class AdminPropertyOut(BaseModel):
    id: str
    name: str
    property_type: str
    city: str
    status: str
    created_at: dt.datetime
    partner_email: str

    model_config = {"from_attributes": True}
