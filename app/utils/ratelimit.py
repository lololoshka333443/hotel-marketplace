"""Fixed-window rate limiter backed by Redis.

Two consumers:
- the channel API (per API key; read and write get separate buckets, writes
  are the dangerous ones);
- webhook delivery (per subscription, so a burst of ours cannot drown a
  partner's server).

If Redis is unreachable we fail *open*: a degraded limiter must not take the
booking path down with it. The skip is logged, and callers still work.

The window is an INCR + EXPIRE in one Lua call, so a burst arriving from
several connections is still counted correctly.
"""

from __future__ import annotations

from app.utils.logger import get_logger
from app.utils.redis import get_redis

log = get_logger(__name__)

# INCR; on the first hit of a window set its TTL. Returns [count, ttl].
_WINDOW_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {c, redis.call('TTL', KEYS[1])}
"""


async def acquire(key: str, limit: int, window_sec: int) -> tuple[bool, int]:
    """Take one slot from a fixed window.

    Returns (allowed, retry_after_sec). retry_after is how long the caller
    should wait before trying again; it is 0 when the call is allowed.
    """
    if limit <= 0:
        # A zero limit means "blocked" — used by tests, and by an operator who
        # wants a channel off without revoking its key.
        return False, max(window_sec, 1)

    try:
        redis = get_redis()
    except RuntimeError:
        # Redis was never initialised (plain unit tests that never boot the app).
        log.debug("ratelimit-skip-no-redis", key=key)
        return True, 0

    try:
        count, ttl = await redis.eval(_WINDOW_LUA, 1, key, window_sec)
        if count <= limit:
            return True, 0
        # ttl is the remaining window, i.e. the earliest the counter resets —
        # the safest advice we can give the caller.
        return False, max(int(ttl), 1)
    except Exception as exc:
        # Never break a business call because the limiter is broken.
        log.warning("ratelimit-failed-open", key=key, error=str(exc))
        return True, 0
