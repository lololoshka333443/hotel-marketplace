import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { admin } from "@/api/client";
import type {
  ReconciliationDeliveryStatus,
  ReconciliationReport,
} from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const STATUS_LABEL: Record<ReconciliationDeliveryStatus, string> = {
  delivered: "Доставлено",
  queued: "В очереди",
  failed: "Ошибка",
  undelivered: "Не доставлено",
  partial: "Частично",
  no_listener: "Некому слушать",
};

const STATUS_VARIANT: Record<
  ReconciliationDeliveryStatus,
  "success" | "neutral" | "error" | "warning"
> = {
  delivered: "success",
  queued: "neutral",
  failed: "error",
  undelivered: "error",
  partial: "warning",
  no_listener: "neutral",
};

const FILTERS: { value: ReconciliationDeliveryStatus | ""; label: string }[] = [
  { value: "", label: "Все" },
  { value: "delivered", label: "Доставлено" },
  { value: "queued", label: "В очереди" },
  { value: "undelivered", label: "Не доставлено" },
  { value: "partial", label: "Частично" },
  { value: "failed", label: "Ошибка" },
  { value: "no_listener", label: "Некому слушать" },
];

/**
 * Did the channel actually get the booking? Every booking pushed in through
 * the channel API, against the delivery of its confirming (or cancelling)
 * event. When a partner says "we never got it", this is the answer.
 */
export function AdminReconciliationPage() {
  useDocumentTitle("Сверка с каналами - админка");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [filter, setFilter] = useState<ReconciliationDeliveryStatus | "">("");

  const { data, isPending, isError, refetch } = useQuery<ReconciliationReport>({
    queryKey: ["admin-reconciliation", dateFrom, dateTo],
    queryFn: ({ signal }) =>
      admin.reconciliation(dateFrom || null, dateTo || null, signal),
  });

  const summary = data?.summary;
  const list =
    data?.bookings.filter(
      (row) => !filter || row.delivery_status === filter,
    ) ?? [];

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Админка
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Сверка с каналами
      </h1>
      <p className="mt-4 text-text-secondary">
        Каждая бронь, которую толкнул канал, против доставки её события: дошло
        ли подтверждение до вебхука партнёра. Если канал говорит «не получили» —
        ответ здесь.
      </p>

      <form
        className="mt-6 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          refetch();
        }}
      >
        <Input
          label="С даты"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <Input
          label="По дату"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
        <Button type="submit" variant="secondary">
          Применить
        </Button>
      </form>

      {summary ? <SummaryStrip summary={summary} /> : null}

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
          Загружаем бронирования…
        </p>
      ) : isError ? (
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <p role="alert" className="text-feedback-error-text">
            Не удалось загрузить сверку. Обновите страницу.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
          >
            Попробовать снова
          </Button>
        </div>
      ) : list.length === 0 ? (
        <p className="mt-10 rounded-xl border border-border-default bg-surface-card p-6 text-text-secondary">
          {data && data.bookings.length > 0
            ? "Броней с таким статусом доставки нет в выбранном диапазоне."
            : "Броней от каналов нет в выбранном диапазоне."}
        </p>
      ) : (
        <ul className="mt-6 space-y-3">
          {list.map((row) => (
            <li
              key={row.booking_id}
              className="rounded-xl border border-border-default bg-surface-card p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm">{row.code}</span>
                    <Badge variant={STATUS_VARIANT[row.delivery_status]}>
                      {STATUS_LABEL[row.delivery_status]}
                    </Badge>
                    <span className="text-xs text-text-tertiary">
                      {row.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {new Date(row.created_at).toLocaleString("ru-RU")} · заезд{" "}
                    {new Date(row.checkin_date).toLocaleDateString("ru-RU")} ·{" "}
                    {row.total_amount.toLocaleString("ru-RU")} ₽
                  </p>
                  {row.event ? (
                    <p className="mt-1 text-xs text-text-tertiary">
                      {row.event.event_type} · доставлено{" "}
                      {row.event.delivered_ok} из {row.event.expected_subscribers}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-text-tertiary">
                      Событие для этой брони не испускалось
                    </p>
                  )}
                  {row.event?.last_error ? (
                    <p
                      role="alert"
                      className="mt-2 rounded-lg bg-surface-sunken p-2 font-mono text-xs text-feedback-error-text"
                    >
                      {row.event.last_error}
                    </p>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SummaryStrip({
  summary,
}: {
  summary: ReconciliationReport["summary"];
}) {
  const cells: { label: string; value: number }[] = [
    { label: "Всего", value: summary.total },
    { label: "Доставлено", value: summary.delivered },
    { label: "В очереди", value: summary.queued },
    { label: "Не доставлено", value: summary.undelivered },
    { label: "Частично", value: summary.partial },
    { label: "Ошибки", value: summary.failed },
    { label: "Некому слушать", value: summary.no_listener },
  ];

  return (
    <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="rounded-xl border border-border-default bg-surface-card p-3"
        >
          <dt className="text-xs text-text-tertiary">{cell.label}</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">
            {cell.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
