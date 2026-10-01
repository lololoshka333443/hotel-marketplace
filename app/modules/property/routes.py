from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.pool import get_pool
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData
from app.modules.property import service
from app.modules.property.schemas import (
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
)
from app.modules.property.unit_type_routes import UnitTypeOut

router = APIRouter(prefix="/v1", tags=["property"])


async def _partner_conn(token: Annotated[TokenData, Depends(require_scope("partner"))]):
    """Acquire a DB connection scoped to the authenticated partner."""
    pool = get_pool()
    conn = await pool.acquire()
    await conn.execute("SELECT set_config('app.partner_id', $1, true)", token.sub)
    try:
        yield conn
    finally:
        await pool.release(conn)


@router.post(
    "/partner/properties",
    response_model=PropertyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_property(
    data: PropertyCreate,
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> PropertyOut:
    conn = await get_pool().acquire()
    try:
        return await service.create_property(conn, token.sub, data)
    finally:
        await get_pool().release(conn)


@router.get("/partner/properties", response_model=list[PropertyOut])
async def list_my_properties(
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> list[PropertyOut]:
    conn = await get_pool().acquire()
    try:
        return await service.get_partner_properties(conn, token.sub)
    finally:
        await get_pool().release(conn)


@router.patch("/partner/properties/{property_id}", response_model=PropertyOut)
async def update_my_property(
    property_id: str,
    data: PropertyUpdate,
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> PropertyOut:
    conn = await get_pool().acquire()
    try:
        result = await service.update_property(conn, property_id, token.sub, data)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="property not found")
        return result
    finally:
        await get_pool().release(conn)


@router.get("/properties", response_model=list[dict])
async def list_public_properties(city: str | None = None) -> list[dict]:
    """Public catalog — only published properties, no partner-internal fields."""
    conn = await get_pool().acquire()
    try:
        return await service.list_public_properties(conn, city)
    finally:
        await get_pool().release(conn)


@router.get("/properties/{property_id}", response_model=dict)
async def get_public_property(property_id: str) -> dict:
    conn = await get_pool().acquire()
    try:
        row = await service.get_public_property(conn, property_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="property not found")
        return row
    finally:
        await get_pool().release(conn)


@router.get("/public/unit-types/{property_id}", response_model=list[UnitTypeOut])
async def list_public_unit_types(property_id: str) -> list[UnitTypeOut]:
    """Public room list for a published property - what the guest books.

    Unauthenticated (this is the catalog); unpublished properties answer 404,
    same as the public property endpoint, so the two never disagree.
    """

    conn = await get_pool().acquire()
    try:
        published = await conn.fetchval(
            "SELECT 1 FROM property WHERE id = $1 AND status = 'published'",
            property_id,
        )
        if not published:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="property not found")
        rows = await conn.fetch(
            "SELECT id::text, property_id::text, name, capacity, total_units "
            "FROM unit_type WHERE property_id = $1 ORDER BY created_at",
            property_id,
        )
        return [UnitTypeOut(**dict(r)) for r in rows]
    finally:
        await get_pool().release(conn)
