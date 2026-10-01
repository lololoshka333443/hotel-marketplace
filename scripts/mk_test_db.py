#!/usr/bin/env python3
"""Provision the throwaway database the test suite runs against.

The suite creates its own database on the fly (see tests/conftest.py), so this
script is only needed where the database has to exist *before* anything else
runs — a CI job that applies migrations as a separate step, or a local check
against a database that must not be the developer's.

The database is created from template0, gets the two trusted extensions the
schema needs, and is migrated through the same runner the app uses. Nothing
else: the suite seeds its own rows and drops the database when it finishes.

    uv run python scripts/mk_test_db.py     # create + migrate hotel_mp_test
    uv run python scripts/mk_test_db.py -f  # drop and rebuild if one is left over

Exit codes: 0 on success, 1 if the database already exists and --force was not
given, 2 if the role cannot create databases.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config.settings import settings  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)


def _admin_dsn(target: str) -> str:
    """Same server and credentials, pointed at the maintenance database."""
    split = urlsplit(target)
    return urlunsplit(split._replace(path="/postgres"))


async def _role_can_create_db(conn: asyncpg.Connection) -> bool:
    return await conn.fetchval(
        "SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user"
    )


async def main(force: bool) -> int:
    target = settings.test_dsn
    if target == settings.database_url:
        print(
            "PYTEST_DISABLE_TEST_DB=1 points the suite at DATABASE_URL.\n"
            "This script would create the *application* database; refusing.",
            file=sys.stderr,
        )
        return 1

    name = urlsplit(target).path.lstrip("/")
    admin = await asyncpg.connect(dsn=_admin_dsn(target))
    try:
        if not await _role_can_create_db(admin):
            print(
                f"Role {await admin.fetchval('SELECT current_user')} cannot CREATE "
                "DATABASE. Grant it, or run the suite against a database the role "
                "already owns.",
                file=sys.stderr,
            )
            return 2

        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name)
        if exists:
            if not force:
                print(
                    f"Database {name} already exists. Use --force to drop and rebuild.",
                    file=sys.stderr,
                )
                return 1
            await admin.execute(f'DROP DATABASE "{name}"')
            log.info("dropped-existing", db=name)

        await admin.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
        log.info("created", db=name)
    finally:
        await admin.close()

    # pgcrypto and citext are trusted extensions, so the application role may
    # create them itself; no superuser required.
    app = await asyncpg.connect(dsn=target)
    try:
        await app.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        await app.execute("CREATE EXTENSION IF NOT EXISTS citext")
    finally:
        await app.close()

    from app.db.migrate import run_migrations

    applied = await run_migrations(dsn=target)
    log.info("migrated", db=name, applied=applied)
    print(f"ready: {target}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-f", "--force", action="store_true", help="drop an existing test database first"
    )
    raise SystemExit(asyncio.run(main(parser.parse_args().force)))
