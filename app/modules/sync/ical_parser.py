"""Minimal RFC 5545 parser for channel calendar imports.

Supports what real channel exports actually contain: VEVENT blocks with
DTSTART/DTEND (date or datetime), line unfolding, UID/SUMMARY, and the common
RRULE subset (FREQ, INTERVAL, COUNT, UNTIL). EXDATE is not supported yet -
documented, not silently ignored: an unsupported rule raises so the sync marks
itself 'error' instead of quietly importing wrong availability.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DATETIME = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$")


@dataclass(frozen=True)
class VEvent:
    uid: str
    summary: str
    start: dt.date
    end: dt.date  # exclusive


class IcalParseError(ValueError):
    """Malformed calendar content."""


def _unfold(text: str) -> list[str]:
    """RFC 5545 line folding: a line beginning with space/tab continues the previous one."""
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t"):
            if not out:
                raise IcalParseError("continuation line without a parent line")
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _parse_date(value: str, name: str) -> dt.date:
    m = _DATE.match(value)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = _DATETIME.match(value)
    if m:
        # A UTC datetime maps to its date; channels are date-granular for us.
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    raise IcalParseError(f"unparsable {name}: {value!r}")


def _property(line: str) -> tuple[str, str, dict[str, str]]:
    """Split 'NAME;PARAM=v;PARAM2=v2:VALUE' -> (name, value, params)."""
    colon = line.find(":")
    if colon < 0:
        raise IcalParseError(f"property without a value: {line!r}")
    head, value = line[:colon], line[colon + 1 :]
    parts = head.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" not in p:
            raise IcalParseError(f"bad parameter in {line!r}")
        k, v = p.split("=", 1)
        params[k.upper()] = v
    return name, value, params


def parse_calendar(text: str) -> list[VEvent]:
    """Parse VEVENTs. Unbounded recurrences are refused (see module docstring)."""
    lines = _unfold(text)
    events: list[VEvent] = []
    props: list[tuple[str, str, dict[str, str]]] = []
    depth = 0

    for line in lines:
        if not line.strip():
            continue
        if line == "BEGIN:VEVENT":
            depth += 1
            if depth != 1:
                raise IcalParseError("nested VEVENT")
            props = []
            continue
        if line == "END:VEVENT":
            depth -= 1
            if depth != 0:
                raise IcalParseError("unbalanced VEVENT")
            events.append(_build_event(props))
            continue
        if depth == 1:
            props.append(_property(line))

    if depth != 0:
        raise IcalParseError("unterminated VEVENT")
    return events


def _build_event(props: list[tuple[str, str, dict[str, str]]]) -> VEvent:
    bag = {name: (value, params) for name, value, params in props}
    if "DTSTART" not in bag:
        raise IcalParseError("VEVENT without DTSTART")

    uid = bag.get("UID", ("", {}))[0]
    summary = bag.get("SUMMARY", ("", {}))[0]

    start = _parse_date(bag["DTSTART"][0], "DTSTART")
    if "DTEND" in bag:
        end = _parse_date(bag["DTEND"][0], "DTEND")
    else:
        end = start + dt.timedelta(days=1)
    if end <= start:
        raise IcalParseError(f"DTEND not after DTSTART for {uid!r}")

    if "RRULE" in bag:
        start, end = _apply_rrule(bag["RRULE"][0], uid, start, end)

    return VEvent(uid=uid, summary=summary, start=start, end=end)


def _apply_rrule(rule: str, uid: str, start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    """Expand the common RRULE subset into a single span covering all instances.

    Returns (first_start, last_end). Anything outside the supported subset
    raises so the sync surfaces the problem instead of mis-importing.
    """
    parts: dict[str, str] = {}
    for chunk in rule.split(";"):
        if "=" not in chunk:
            raise IcalParseError(f"bad RRULE chunk in {uid!r}: {chunk!r}")
        k, v = chunk.split("=", 1)
        parts[k.upper()] = v.upper()

    freq = parts.get("FREQ")
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        raise IcalParseError(f"unsupported RRULE FREQ in {uid!r}: {freq!r}")
    interval = int(parts.get("INTERVAL", "1"))
    if interval < 1:
        raise IcalParseError(f"bad RRULE INTERVAL in {uid!r}")

    step = {
        "DAILY": dt.timedelta(days=interval),
        "WEEKLY": dt.timedelta(weeks=interval),
        "MONTHLY": None,
        "YEARLY": None,
    }[freq]

    if "COUNT" not in parts and "UNTIL" not in parts:
        raise IcalParseError(f"unbounded RRULE in {uid!r} - needs COUNT or UNTIL")

    until = _parse_until(parts.get("UNTIL"))
    count = int(parts["COUNT"]) if "COUNT" in parts else None
    duration = end - start

    # The first instance is the VEVENT itself; walk the recurrences from there.
    current = start
    last_end = end
    n = 1
    while True:
        if count is not None and n >= count:
            break
        current, shifted = _advance(freq, step, current, interval)
        if not shifted:
            break
        if until is not None and current > until:
            break
        n += 1
        last_end = max(last_end, current + duration)
        if current > dt.date(2100, 1, 1):
            raise IcalParseError(f"RRULE ran past 2100 in {uid!r} - needs COUNT or UNTIL")

    return start, last_end


def _advance(freq, step, current: dt.date, interval: int) -> tuple[dt.date, bool]:
    if freq in ("MONTHLY", "YEARLY"):
        months = interval if freq == "MONTHLY" else interval * 12
        y = current.year + (current.month - 1 + months) // 12
        m = (current.month - 1 + months) % 12 + 1
        try:
            return dt.date(y, m, min(current.day, 28)), True
        except ValueError:
            return current, False
    return current + step, True


def _parse_until(value: str | None) -> dt.date | None:
    if value is None:
        return None
    return _parse_date(value, "UNTIL")


def expand_dates(events: list[VEvent], date_from: dt.date, date_to: dt.date) -> set[dt.date]:
    """Blocked dates inside [date_from, date_to)."""
    out: set[dt.date] = set()
    for ev in events:
        d = ev.start
        while d < ev.end and d < date_to:
            if d >= date_from:
                out.add(d)
            d += dt.timedelta(days=1)
    return out
