from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.pool import get_pool
from app.modules.admin import report
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/reports/commission")
async def commission_report(
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    token: Annotated[TokenData, Depends(require_scope("admin"))] = None,
) -> dict:
    """Commission accrued per partner. Admin scope only."""
    conn = await get_pool().acquire()
    try:
        return await report.commission_report(conn, date_from, date_to)
    finally:
        await get_pool().release(conn)
