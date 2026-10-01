from __future__ import annotations

import datetime as dt
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db.pool import get_pool
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData
from app.modules.inventory import service

router = APIRouter(prefix="/v1/partner/unit-types", tags=["unit-types"])


class UnitTypeCreate(BaseModel):
    property_id: str
    name: str = Field(min_length=2, max_length=120)
    capacity: int = Field(default=2, ge=1)
    total_units: int = Field(default=1, ge=1)


class UnitTypeOut(BaseModel):
    id: str
    property_id: str
    name: str
    capacity: int
    total_units: int


async def _get_owned(conn: asyncpg.Connection, unit_type_id: str, partner_id: str) -> str:
    """Return property id if the partner owns this unit type, else ''."""
    return (
        await conn.fetchval(
            "SELECT ut.property_id::text FROM unit_type ut "
            "JOIN property p ON p.id = ut.property_id "
            "WHERE ut.id = $1 AND p.partner_id = $2",
            unit_type_id,
            partner_id,
        )
        or ""
    )


@router.post("", response_model=UnitTypeOut, status_code=status.HTTP_201_CREATED)
async def create_unit_type(
    data: UnitTypeCreate,
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> UnitTypeOut:
    conn = await get_pool().acquire()
    try:
        owned = await conn.fetchval(
            "SELECT 1 FROM property WHERE id = $1 AND partner_id = $2",
            data.property_id,
            token.sub,
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="property not found")
        row = await conn.fetchrow(
            "INSERT INTO unit_type (property_id, name, capacity, total_units) "
            "VALUES ($1, $2, $3, $4) RETURNING id::text, property_id::text, name, capacity, total_units",
            data.property_id,
            data.name,
            data.capacity,
            data.total_units,
        )
        assert row is not None
        # Generate inventory immediately so the calendar is never empty.
        await service.ensure_inventory(conn, row["id"])
        return UnitTypeOut(
            id=row["id"],
            property_id=row["property_id"],
            name=row["name"],
            capacity=row["capacity"],
            total_units=row["total_units"],
        )
    finally:
        await get_pool().release(conn)


@router.get("/property/{property_id}", response_model=list[UnitTypeOut])
async def list_unit_types(
    property_id: str,
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> list[UnitTypeOut]:
    conn = await get_pool().acquire()
    try:
        owned = await conn.fetchval(
            "SELECT 1 FROM property WHERE id = $1 AND partner_id = $2",
            property_id,
            token.sub,
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="property not found")
        rows = await conn.fetch(
            "SELECT id::text, property_id::text, name, capacity, total_units "
            "FROM unit_type WHERE property_id = $1 ORDER BY created_at",
            property_id,
        )
        return [UnitTypeOut(**dict(r)) for r in rows]
    finally:
        await get_pool().release(conn)

_ = dt
