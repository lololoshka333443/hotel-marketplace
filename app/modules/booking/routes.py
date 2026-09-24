from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.db.pool import get_pool
from app.modules.booking import service
from app.modules.booking.schemas import HoldRequest

router = APIRouter(prefix="/v1/bookings", tags=["booking"])


def _line_dates(conn, booking_id: str):
    return conn.fetch(
        "SELECT date, price::float8 FROM booking_line WHERE booking_id = $1 ORDER BY date",
        booking_id,
    )


@router.post("/hold", status_code=status.HTTP_201_CREATED)
async def create_hold(
    data: HoldRequest,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> dict:
    """Create a time-limited hold on inventory.

    Returns 409 when the dates are not available (including the stop-sell case)
    or when the idempotency key collides with a different payload.
    """
    pool = get_pool()
    conn = await pool.acquire()
    try:
        async with conn.transaction(isolation="serializable"):
            try:
                row = await service.create_hold(
                    conn,
                    unit_type_id=data.unit_type_id,
                    checkin=data.checkin,
                    checkout=data.checkout,
                    guest_name=data.guest.name,
                    guest_email=str(data.guest.email),
                    guest_phone=data.guest.phone,
                    idempotency_key=idempotency_key,
                )
            except service.NotAvailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"dates not available: {exc}",
                ) from exc
            except service.Conflict as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"idempotency conflict: {exc}",
                ) from exc

            lines = await _line_dates(conn, row["id"])
            return {
                "id": row["id"],
                "code": row["code"],
                "status": row["status"],
                "total_amount": float(row["total_amount"]),
                "hold_expires_at": row["hold_expires_at"].isoformat(),
                "checkin_date": data.checkin.isoformat(),
                "checkout_date": data.checkout.isoformat(),
                "lines": [{"date": ln["date"].isoformat(), "price": ln["price"]} for ln in lines],
            }
    finally:
        await pool.release(conn)


@router.get("/{booking_id}")
async def get_booking(booking_id: str) -> dict:
    conn = await get_pool().acquire()
    try:
        row = await conn.fetchrow(
            """
            SELECT id::text, code, status, total_amount::float8, hold_expires_at,
                   checkin_date, checkout_date, unit_type_id::text
            FROM booking WHERE id = $1
            """,
            booking_id,
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="booking not found")
        lines = await _line_dates(conn, booking_id)
        return {
            "id": row["id"],
            "code": row["code"],
            "status": row["status"],
            "total_amount": row["total_amount"],
            "hold_expires_at": row["hold_expires_at"].isoformat()
            if row["hold_expires_at"]
            else None,
            "checkin_date": row["checkin_date"].isoformat(),
            "checkout_date": row["checkout_date"].isoformat(),
            "lines": [{"date": ln["date"].isoformat(), "price": ln["price"]} for ln in lines],
        }
    finally:
        await get_pool().release(conn)


@router.post("/{booking_id}/cancel")
async def cancel_booking(booking_id: str) -> dict:
    """Cancel a hold and return inventory to the pool."""
    pool = get_pool()
    conn = await pool.acquire()
    try:
        async with conn.transaction(isolation="serializable"):
            await service.release_hold(conn, booking_id)
            status_now = await conn.fetchval("SELECT status FROM booking WHERE id = $1", booking_id)
        return {"id": booking_id, "status": status_now}
    finally:
        await pool.release(conn)
