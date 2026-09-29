import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { admin } from "@/api/client";
import type { OutboxEvent } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Все" },
  { value: "pending", label: "В очереди" },
  { value: "delivering", label: "В доставке" },
  { value: "published", label: "Доставлено" },
  { value: "failed", label: "Ошибки" },
];

const STATUS_LABEL: Record<OutboxEvent["status"], string> = {
  pending: "В очереди",
  delivering: "В доставке",
  published: "Доставлено",
  failed: "Ошибка",
};

const STATUS_VARIANT: Record<OutboxEvent["status"], BadgeVariant> = {
  pending: "neutral",
  delivering: "warning",
  published: "success",
  failed: "error",
};

type BadgeVariant = "success" | "warning" | "error" | "neutral";

/**
 * Outbox ledger: every event we pushed out, per subscription. This is the
 * reconciliation view — when a channel says "we never got the booking", this
 * is where you look.
 */
export function AdminOutboxPage() {
  useDocumentTitle("Доставка событий - админка");
  const [filter, setFilter] = useState("");
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-outbox", filter],
    queryFn: ({ signal }) => admin.outbox(filter || null, signal),
  });

  const retry = useMutation({
    mutationFn: (eventId: string) => admin.retryEvent(eventId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["admin-outbox"] }),
  });

  const list = data ?? [];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Доставка событий</h1>
      <p className="mt-2 text-text-secondary">
        Каждое событие наружу: бронь, цена, доступность. Если канал не получил
        его — здесь видно почему и когда была последняя попытка.
      </p>

      <OutboxMetricsStrip />

      <div className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Button
            key={f.value}
            variant={filter === f.value ? "primary" : "secondary"}
            size="sm"
            selected={filter === f.value}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {isPending ? (
        <p role="status" className="mt-10 text-text-secondary">
          Загружаем события…
        </p>
      ) : isError ? (
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <p role="alert" className="text-feedback-error-text">
            Не удалось загрузить события. Обновите страницу.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ["admin-outbox"] })
            }
          >
            Попробовать снова
          </Button>
        </div>
      ) : list.length === 0 ? (
        <p className="mt-10 rounded-lg border border-border-default bg-surface-card p-6 text-text-secondary">
          Событий нет. Они появляются, когда партнёр подключает вебхук и
          происходят изменения.
        </p>
      ) : (
        <ul className="mt-6 space-y-3">
          {list.map((event) => (
            <li
              key={event.id}
              className="rounded-lg border border-border-default bg-surface-card p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm">{event.event_type}</span>
                    <Badge variant={STATUS_VARIANT[event.status]}>
                      {STATUS_LABEL[event.status]}
                    </Badge>
                    <span className="text-xs text-text-tertiary">
                      попытка {event.attempts}/{event.max_attempts}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {new Date(event.happened_at).toLocaleString("ru-RU")}
                    {event.published_at
                      ? ` · доставлено ${new Date(event.published_at).toLocaleString("ru-RU")}`
                      : ""}
                  </p>
                  <p className="mt-1 font-mono text-xs text-text-secondary">
                    {event.aggregate}: {event.aggregate_id}
                  </p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    доставлено {event.delivered_ok} · ошибок {event.delivered_fail}
                  </p>
                  {event.last_error ? (
                    <p
                      role="alert"
                      className="mt-2 rounded bg-surface-sunken p-2 font-mono text-xs text-feedback-error-text"
                    >
                      {event.last_error}
                    </p>
                  ) : null}
                </div>
                {event.status === "failed" ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={retry.isPending}
                    onClick={() => retry.mutate(event.id)}
                  >
                    Повторить
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {retry.isError ? (
        <p role="alert" className="mt-4 text-sm text-feedback-error-text">
          Не удалось поставить событие в очередь. Попробуйте ещё раз.
        </p>
      ) : null}
    </div>
  );
}

/**
 * Queue health at a glance: is the queue keeping up, and is anything stuck?
 */
function OutboxMetricsStrip() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-outbox-metrics"],
    queryFn: ({ signal }) => admin.outboxMetrics(signal),
    refetchInterval: 15_000,
  });

  if (isPending) {
    return (
      <p role="status" className="mt-6 text-sm text-text-secondary">
        Загружаем метрики очереди…
      </p>
    );
  }

  if (isError || !data) {
    return (
      <p className="mt-6 text-sm text-text-tertiary">
        Метрики очереди недоступны — список событий ниже по-прежнему можно
        смотреть.
      </p>
    );
  }

  const cells: { label: string; value: string }[] = [
    {
      label: "В очереди",
      value: `${data.pending} / ${data.depth_limit}`,
    },
    { label: "В доставке", value: String(data.delivering) },
    {
      label: "Ждут ретрая",
      value: String(data.scheduled_for_retry),
    },
    { label: "Ошибки", value: String(data.failed) },
    {
      label: "Медианная задержка",
      value: data.median_latency_sec ? `${data.median_latency_sec} с` : "—",
    },
    {
      label: "Самое старое в очереди",
      value: data.oldest_pending_sec ? `${data.oldest_pending_sec} с` : "—",
    },
    {
      label: "Сброшено лимитом",
      value: String(data.shed_total),
    },
    {
      label: "Воркеры доставки",
      value: `${data.workers} × ${data.shard_count} шард.`,
    },
  ];

  // The queue is older than the configured lag: events are arriving faster
  // than the worker can push them out, so something is falling behind.
  const isLagging =
    data.oldest_pending_sec >= data.lag_alert_sec && data.pending > 0;
  // At the depth limit, bulk events are being shed right now — bookings still
  // go out, but the channels must pull rates and availability themselves.
  const isShedding = data.pending >= data.depth_limit;

  return (
    <div className="mt-6 space-y-3">
      {isLagging || isShedding ? (
        <div
          role="alert"
          className="rounded-lg border border-border-default bg-feedback-warning-bg p-3 text-sm text-feedback-warning-text"
        >
          {isShedding
            ? "Очередь достигла лимита — массовые события (цены, доступность) сбрасываются, пока воркер не разгребет отставание. Бронирования доставляются как обычно, тарифы канал забирает через read-API."
            : `Очередь отстаёт: самое старое событие ждёт уже ${Math.round(
                data.oldest_pending_sec / 60,
              )} мин. Стоит проверить работоспособность вебхуков партнёра.`}
        </div>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="rounded-lg border border-border-default bg-surface-card p-3"
          >
            <dt className="text-xs text-text-tertiary">{cell.label}</dt>
            <dd className="mt-1 text-lg font-semibold tabular-nums">
              {cell.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
