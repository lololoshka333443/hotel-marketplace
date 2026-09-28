-- 0016__outbox_backlog_limit.sql
-- The outbox cannot grow without bound either.
--
-- A mass operation (bulk price load, an iCal import of a whole season) can
-- throw thousands of events at the queue. The worker drains it at
-- webhook_rate_per_sec per subscription, so those events sit in front of a
-- booking and the partner's channel learns about the booking late — the one
-- thing that actually costs money.
--
-- Two changes bound the damage:
--
-- * priority. booking.* is high (a booking is money and it is the source of
--   truth, so it is never delayed and never dropped), everything else is low.
--   claim_due takes the highest-priority due rows first, so a booking jumps
--   the whole backlog.
-- * shedding. When the queue is deeper than the configured limit, a low-
--   priority event is not emitted at all: it is counted and dropped. The
--   channels it was meant for can pull current rates and availability through
--   the channel read-API and iCal, so a dropped notification is recovered by
--   the next pull — a booking is never subject to this.
--
-- The counter is a gauge for the staff, not a second queue: one row per
-- (aggregate, event_type), bounded by the number of event types we emit.

ALTER TABLE outbox_event
    ADD COLUMN IF NOT EXISTS priority smallint NOT NULL DEFAULT 9;

-- Backfill what is already queued: bookings jump the backlog, everything
-- else keeps its place as low priority.
UPDATE outbox_event SET priority = 1 WHERE aggregate = 'booking';

-- claim_due orders by priority, then due time, then age. The old index served
-- the due scan; this one serves the ordering too.
DROP INDEX IF EXISTS idx_outbox_due;
CREATE INDEX idx_outbox_due
    ON outbox_event (priority, next_attempt_at, happened_at)
    WHERE status IN ('pending','delivering');

CREATE TABLE IF NOT EXISTS outbox_shed_counter (
    aggregate    text        NOT NULL,
    event_type   text        NOT NULL,
    n            int         NOT NULL DEFAULT 0,
    last_shed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aggregate, event_type)
);

COMMENT ON COLUMN outbox_event.priority IS
    '1 = booking (никогда не задерживается и не сбрасывается), 9 = массовые события';
COMMENT ON TABLE outbox_shed_counter IS
    'Счётчик сброшенных при перегрузке событий — gauge для админки, не очередь';
