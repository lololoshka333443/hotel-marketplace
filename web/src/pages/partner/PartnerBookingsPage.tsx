import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";

import { getToken, partner } from "@/api/client";
import { humanError } from "@/utils/errors";
import type { BookingStatus } from "@/api/types";
import { plural } from "@/utils/plural";
import { daysBetween } from "@/utils/date";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Все" },
  { value: "confirmed", label: "Подтверждены" },
  { value: "hold", label: "Ожидают оплаты" },
  { value: "cancelled", label: "Отменены" },
  { value: "refunded", label: "Возврат" },
];

const STATUS_LABEL: Record<BookingStatus, string> = {
  hold: "Ожидает оплаты",
  paid: "Оплачена",
  confirmed: "Подтверждена",
  cancelled: "Отменена",
  failed: "Не удалась",
  conflict: "Конфликт",
  no_show: "Не приехал",
  refunded: "Возврат",
};

/** Type colour per status, so the row reads at a glance. */
function badgeVariant(status: BookingStatus) {
  switch (status) {
    case "confirmed":
      return "success" as const;
    case "hold":
    case "paid":
      return "warning" as const;
    case "cancelled":
    case "failed":
    case "conflict":
    case "no_show":
      return "neutral" as const;
    case "refunded":
      return "error" as const;
  }
}

/** Nights in a stay: checkout is not a night, so `[checkin, checkout)`. */
function nights(checkin: string, checkout: string): number {
  return daysBetween(checkin, checkout);
}

/** Бронирования на моих объектах. */
export function PartnerBookingsPage() {
  useDocumentTitle("Бронирования - кабинет партнёра");
  const [filter, setFilter] = useState("");

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["partner-bookings", filter],
    queryFn: ({ signal }) => partner.bookings.list(filter || null, signal),
    enabled: Boolean(getToken()),
  });

  const list = data ?? [];

  // The login form lives on /login; it sends the partner back here on success.
  if (!getToken()) {
    return <Navigate to="/login" state={{ from: "/partner/bookings" }} replace />;
  }
  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Кабинет партнёра
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Бронирования
      </h1>
      <p className="mt-4 text-text-secondary">
        Кто едет к вам, на какие даты и как бронь до вас дошла. Код брони видит
        гость — он нужен, чтобы связаться с нами.
      </p>

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
            {humanError(error, "Не удалось загрузить бронирования.")}
          </p>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Попробовать снова
          </Button>
        </div>
      ) : list.length === 0 ? (
        <p className="mt-10 rounded-xl border border-border-default bg-surface-card p-6 text-text-secondary">
          {filter
            ? "По этому фильтру броней нет."
            : "Броней пока нет. Как только гость забронирует, он появится здесь."}
        </p>
      ) : (
        <ul className="mt-6 space-y-3">
          {list.map((booking) => (
            <li
              key={booking.id}
              className="flex flex-col gap-3 rounded-xl border border-border-default bg-surface-card p-4 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-mono text-lg font-medium">
                    {booking.code}
                  </h2>
                  <Badge variant={badgeVariant(booking.status)}>
                    {STATUS_LABEL[booking.status]}
                  </Badge>
                  {booking.origin === "channel" ? (
                    <Badge variant="primary">
                      канал{booking.source_channel ? ` · ${booking.source_channel}` : ""}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {booking.property_name} · {booking.unit_type_name} ·{" "}
                  {nights(booking.checkin_date, booking.checkout_date)}{" "}
                  {plural(
                    nights(booking.checkin_date, booking.checkout_date),
                    "ночь",
                    "ночи",
                    "ночей",
                  )}
                </p>
                <p className="mt-1 text-sm text-text-secondary">
                  Заезд {new Date(booking.checkin_date).toLocaleDateString("ru-RU")} ·
                  выезд {new Date(booking.checkout_date).toLocaleDateString("ru-RU")}
                </p>
                <p className="mt-1 text-sm text-text-secondary">
                  {booking.guest_name} · {booking.guest_email} ·{" "}
                  {booking.guest_phone}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-lg font-medium">
                  {booking.total_amount.toLocaleString("ru-RU")} ₽
                </p>
                <p className="mt-1 text-sm text-text-secondary">
                  комиссия {booking.commission_amount.toLocaleString("ru-RU")} ₽
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
