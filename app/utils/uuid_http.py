"""A UUID path parameter that is not a UUID must answer 404, not a 500.

Postgres rejects a malformed uuid with `InvalidTextRepresentationError` —
asyncpg wraps it as `DataError` — so every endpoint taking an id straight to a
query leaks a stack trace on `/v1/properties/not-a-uuid`. The id does not exist,
which is exactly what 404 already means for a well-formed but unknown one.

Catching this in one exception handler covers the whole API; auditing each
route for which parameter is typed as uuid would be the same answer with more
moving parts.
"""

from __future__ import annotations

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def install_uuid_handler(app: FastAPI) -> None:
    @app.exception_handler(asyncpg.DataError)
    async def _on_bad_uuid(_: Request, exc: asyncpg.DataError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "not found"})
