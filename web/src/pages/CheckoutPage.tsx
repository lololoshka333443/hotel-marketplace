import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertCircle, CheckCircle2, Clock } from "lucide-react";

import { bookings } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { useCountdown, formatCountdown } from "@/hooks/useCountdown";

export function CheckoutPage() {
  const { bookingId } = useParams();
  const navigate = useNavigate();

  const { data: booking, isPending, isError, error } = useQuery({
    queryKey: ["booking", bookingId],
    queryFn: ({ signal }) => bookings.get(bookingId as string, signal),
    enabled: Boolean(bookingId),
    // The hold ticks down; re-fetch keeps the status honest if it expires.
    refetchInterval: 30_000,
  });

  const pay = useMutation({
    mutationFn: () => bookings.pay(bookingId as string),
    onSuccess: (data) => {
      if (data.status === "confirmed") navigate(`/booking/${data.id}/success`);
    },
  });

  const msLeft = useCountdown(booking?.hold_expires_at);
  const isHold = booking?.status === "hold";
  const isConfirmed = booking?.status === "confirmed";
  const expired = isHold && msLeft === 0;

  // While the hold is live the guest keeps the price; after expiry it lapses.
  const expiredOrPaid = expired || isConfirmed;

  if (isPending) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-12 text-text-secondary">
        Загружаем бронь…
      </div>
    );
  }

  if (isError || !booking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-12">
        <h1 className="text-2xl font-bold">Бронь не найдена</h1>
        <p className="mt-2 text-text-secondary">
          Возможно, ссылка устарела.{" "}
          {error instanceof Error ? `(${error.message})` : ""}
        </p>
        <Link to="/search" className="mt-6 inline-block">
          <Button variant="secondary">Вернуться к поиску</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight">Оплата брони</h1>
      <p className="mt-1 font-mono text-sm text-text-secondary">{booking.code}</p>

      {isConfirmed ? <ConfirmedState /> : null}
      {expired ? <ExpiredState bookingId={booking.id} /> : null}

      <section className="mt-6 rounded-lg border border-border-default bg-surface-card p-6">
        <h2 className="text-lg font-semibold">Ваша бронь</h2>
        <dl className="mt-4 space-y-2 text-sm">
          <Row label="Заезд">{booking.checkin_date}</Row>
          <Row label="Выезд">{booking.checkout_date}</Row>
          <Row label="Сумма">
            <strong>{booking.total_amount.toFixed(0)} ₽</strong>
          </Row>
        </dl>

        {booking.lines.length > 0 ? (
          <div className="mt-6 border-t border-border-default pt-4">
            <h3 className="text-sm font-medium text-text-secondary">
              Посуточно
            </h3>
            <ul className="mt-2 space-y-1 text-sm">
              {booking.lines.map((line) => (
                <li
                  key={line.date}
                  className="flex justify-between gap-4 text-text-secondary"
                >
                  <span>{line.date}</span>
                  <span>{line.price.toFixed(0)} ₽</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {isHold && !expiredOrPaid ? (
          <div className="mt-6 flex items-center gap-2 rounded-button bg-feedback-info-bg px-4 py-3 text-sm text-feedback-info-text">
            <Clock className="size-4 shrink-0" aria-hidden="true" />
            <span>
              Цена зафиксирована ещё{" "}
              <strong aria-live="polite">{formatCountdown(msLeft)}</strong>. Потом
              бронь аннулируется.
            </span>
          </div>
        ) : null}

        <div className="mt-6">
          <Button
            onClick={() => pay.mutate()}
            disabled={!isHold || expired || pay.isPending}
            loading={pay.isPending}
            className="w-full"
            size="lg"
          >
            Оплатить {booking.total_amount.toFixed(0)} ₽
          </Button>
          {pay.isError ? (
            <p
              role="alert"
              className="mt-3 flex items-center gap-2 text-sm text-feedback-error-text"
            >
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
              {pay.error instanceof Error
                ? pay.error.message
                : "Не удалось оплатить. Попробуйте ещё раз."}
            </p>
          ) : null}
          <p className="mt-3 text-center text-xs text-text-tertiary">
            100% предоплата. Отмена бесплатна до 24:00 дня заезда.
          </p>
        </div>
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="text-text-primary">{children}</dd>
    </div>
  );
}

function ConfirmedState() {
  return (
    <div className="mt-6 flex items-start gap-3 rounded-lg border border-border-default bg-feedback-success-bg p-4 text-feedback-success-text">
      <CheckCircle2 className="size-5 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">Бронь подтверждена</p>
        <p className="mt-1 text-sm">
          Мгновенное подтверждение. Данные отправлены на почту.
        </p>
      </div>
    </div>
  );
}

function ExpiredState({ bookingId }: { bookingId: string }) {
  return (
    <div className="mt-6 flex items-start gap-3 rounded-lg border border-border-default bg-feedback-error-bg p-4 text-feedback-error-text">
      <AlertCircle className="size-5 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">Время оплаты истекло</p>
        <p className="mt-1 text-sm">
          Бронь {bookingId.slice(0, 8)} аннулирована. Даты могли быть заняты -
          выберите их заново.
        </p>
      </div>
    </div>
  );
}
