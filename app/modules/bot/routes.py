"""The partner's Telegram binding, read from the cabinet.

The code is the secret the partner copies into the bot; the chat id is what the
partner sees after linking. Rotating gives a fresh code without unlinking —
useful when the old one was shared in a chat.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.pool import get_pool
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData

router = APIRouter(prefix="/v1/partner", tags=["telegram"])


class TelegramStatus(BaseModel):
    link_code: str
    chat_id: str | None = None
    linked_at: str | None = None


@router.get("/telegram", response_model=TelegramStatus)
async def get_telegram_status(
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> dict:
    """The linking code plus the chat currently bound to this partner."""
    conn = await get_pool().acquire()
    try:
        row = await conn.fetchrow(
            """
            SELECT telegram_link_code::text AS link_code,
                   telegram_chat_id::text   AS chat_id,
                   telegram_linked_at::text AS linked_at
            FROM partner WHERE id = $1
            """,
            token.sub,
        )
    finally:
        await get_pool().release(conn)
    return dict(row)


@router.post("/telegram/rotate", response_model=TelegramStatus)
async def rotate_telegram_code(
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> dict:
    """Issue a fresh linking code. The old one stops working at once."""
    conn = await get_pool().acquire()
    try:
        row = await conn.fetchrow(
            """
            UPDATE partner
            SET telegram_link_code = gen_random_uuid()::text
            WHERE id = $1
            RETURNING telegram_link_code::text AS link_code,
                      telegram_chat_id::text   AS chat_id,
                      telegram_linked_at::text AS linked_at
            """,
            token.sub,
        )
    finally:
        await get_pool().release(conn)
    return dict(row)


@router.delete("/telegram", response_model=TelegramStatus)
async def unlink_telegram(
    token: Annotated[TokenData, Depends(require_scope("partner"))],
) -> dict:
    """Forget the chat. The code is rotated too: it may have been shared."""
    conn = await get_pool().acquire()
    try:
        row = await conn.fetchrow(
            """
            UPDATE partner
            SET telegram_chat_id = NULL,
                telegram_linked_at = NULL,
                telegram_link_code = gen_random_uuid()::text
            WHERE id = $1
            RETURNING telegram_link_code::text AS link_code,
                      telegram_chat_id::text   AS chat_id,
                      telegram_linked_at::text AS linked_at
            """,
            token.sub,
        )
    finally:
        await get_pool().release(conn)
    return dict(row)
