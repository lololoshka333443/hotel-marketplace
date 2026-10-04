"""Telegram bot tests: linking a partner's chat, and the code rotating.

The code is the secret of the binding. It must work once, stop working after a
link, and rotate without unlinking a chat that is already bound.
"""

import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.bot import _link, _unlink


async def _make_partner(conn, email: str, name: str = "Tester") -> str:
    return await auth_service.register_partner(
        conn, PartnerRegisterRequest(email=email, password="secret123", name=name)
    )


async def _link_code(conn, partner_id: str) -> str:
    return await conn.fetchval("SELECT telegram_link_code FROM partner WHERE id = $1", partner_id)


# ------------------------------------------------------------------ linking


@pytest.mark.asyncio
async def test_start_binds_chat_and_rotates_code(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "tg1@example.com")
    code = await _link_code(db_conn, partner_id)

    name = await _link(db_conn, code, "999")

    assert name == "Tester"
    row = await db_conn.fetchrow(
        "SELECT telegram_chat_id, telegram_linked_at, telegram_link_code"
        " FROM partner WHERE id = $1",
        partner_id,
    )
    assert row["telegram_chat_id"] == "999"
    assert row["telegram_linked_at"] is not None
    # The code used is spent: a replay cannot rebind the chat.
    assert row["telegram_link_code"] != code


@pytest.mark.asyncio
async def test_start_without_code_binds_nothing(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "tg2@example.com")

    assert await _link(db_conn, "", "999") is None
    assert await _link(db_conn, "   ", "999") is None

    chat = await db_conn.fetchval("SELECT telegram_chat_id FROM partner WHERE id = $1", partner_id)
    assert chat is None


@pytest.mark.asyncio
async def test_start_unknown_code_binds_nothing(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "tg3@example.com")

    assert await _link(db_conn, "no-such-code", "999") is None

    chat = await db_conn.fetchval("SELECT telegram_chat_id FROM partner WHERE id = $1", partner_id)
    assert chat is None


@pytest.mark.asyncio
async def test_spent_code_does_not_rebind(db_conn) -> None:
    """A second /start with the consumed code finds nothing."""
    partner_id = await _make_partner(db_conn, "tg4@example.com")
    code = await _link_code(db_conn, partner_id)

    assert await _link(db_conn, code, "111") == "Tester"
    # The row rotated, so the old code is gone from the table.
    assert await _link(db_conn, code, "222") is None

    chat = await db_conn.fetchval("SELECT telegram_chat_id FROM partner WHERE id = $1", partner_id)
    assert chat == "111"


# ----------------------------------------------------------------- unlinking


@pytest.mark.asyncio
async def test_unlink_forgets_chat(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "tg5@example.com", "Отель")
    code = await _link_code(db_conn, partner_id)
    await _link(db_conn, code, "333")

    name = await _unlink(db_conn, "333")

    assert name == "Отель"
    row = await db_conn.fetchrow(
        "SELECT telegram_chat_id, telegram_linked_at FROM partner WHERE id = $1",
        partner_id,
    )
    assert row["telegram_chat_id"] is None
    assert row["telegram_linked_at"] is None


@pytest.mark.asyncio
async def test_unlink_unknown_chat_is_a_no_op(db_conn) -> None:
    await _make_partner(db_conn, "tg6@example.com")

    assert await _unlink(db_conn, "404") is None


@pytest.mark.asyncio
async def test_codes_are_unique_across_partners(db_conn) -> None:
    """Two partners never share a code — /start binds one chat to one partner."""
    a = await _make_partner(db_conn, "tg7a@example.com")
    b = await _make_partner(db_conn, "tg7b@example.com")

    code_a = await _link_code(db_conn, a)
    code_b = await _link_code(db_conn, b)

    assert code_a != code_b
