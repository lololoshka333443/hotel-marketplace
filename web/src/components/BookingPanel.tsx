import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CalendarDays } from "lucide-react";

import { bookings, availability } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { AvailabilityDay } from "@/api/types";

interface BookingPanelProps {
  unitTypeId: string;
  currency: string;
}

/**
 * Booking panel: pick dates, see per-night availability and total, then place
 * a hold. Hold TTL is 15 minutes; the checkout page counts it down and the
 * payment confirms. The guest never sees the commission.
 */
export function BookingPanel({ unitTypeId, currency }: BookingPanelProps) {
  const navigate = useNavigate();
  const [checkin, setCheckin] = useState("");
  const [checkout, setCheckout] = useState("");
  const [days, setDays] = useState<AvailabilityDay[] | null>(null);

  const price = useMutation({
    mutationFn: () =>
      availability.get(unitTypeId, checkin, addDays(checkout, -1)),
    onSuccess: (data) => setDays(data.days),
  });

  const hold = useMutation({
    mutationFn: () =>
      bookings.hold(
        { unit_type_id: unitTypeId, checkin, checkout, guest: GUEST },
        `hold-${unitTypeId}-${checkin}-${checkout}`,
      ),
    onSuccess: (data) => navigate(`/checkout/${data.id}`),
  });

  const total = days ? days.reduce((s, d) => s + (d.price ?? 0), 0) : 0;
  const blocked = days?.some((d) => !d.available) ?? false;
  const canBook = Boolean(checkin && checkout) && !blocked;

  function onCheck() {
    if (!checkin || !checkout) return;
    price.mutate();
  }

  return (
    <section className="rounded-lg border border-border-default bg-surface-card p-6">
      <h2 className="text-lg font-semibold">Бронирование</h2>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-text-secondary">Заезд</span>
          <Input
            type="date"
            value={checkin}
            onChange={(e) => setCheckin(e.target.value)}
            min={today()}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-text-secondary">Выезд</span>
          <Input
            type="date"
            value={checkout}
            onChange={(e) => setCheckout(e.target.value)}
            min={checkin || today()}
          />
        </label>
      </div>

      <div className="mt-4">
        <Button
          variant="secondary"
          onClick={onCheck}
          loading={price.isPending}
          disabled={!checkin || !checkout}
          className="w-full"
        >
          <CalendarDays className="size-4" aria-hidden="true" />
          Проверить даты
        </Button>
        {price.isError ? (
          <p
            role="alert"
            className="mt-3 text-sm text-feedback-error-text"
          >
            Не удалось проверить даты. Обновите страницу и попробуйте снова.
          </p>
        ) : null}
      </div>

      {days ? (
        <div className="mt-4 border-t border-border-default pt-4 text-sm">
          {blocked ? (
            <p className="flex items-center gap-2 text-feedback-error-text">
              На выбранные даты мест нет. Попробуйте другие.
            </p>
          ) : (
            <>
              <div className="flex justify-between">
                <span className="text-text-secondary">
                  {days.length} {plural(days.length, "ночь", "ночи", "ночей")}
                </span>
                <strong>
                  {total.toFixed(0)} {currency}
                </strong>
              </div>
              <ul className="mt-2 space-y-1">
                {days.map((d) => (
                  <li
                    key={d.date}
                    className="flex justify-between text-text-secondary"
                  >
                    <span>{d.date}</span>
                    <span>{(d.price ?? 0).toFixed(0)} {currency}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : null}

      <div className="mt-5">
        <Button
          onClick={() => hold.mutate()}
          disabled={!canBook || hold.isPending}
          loading={hold.isPending}
          size="lg"
          className="w-full"
        >
          Забронировать
        </Button>
        {hold.isError ? (
          <p
            role="alert"
            className="mt-3 text-sm text-feedback-error-text"
          >
            {hold.error instanceof Error
              ? hold.error.message
              : "Не удалось забронировать. Попробуйте ещё раз."}
          </p>
        ) : null}
        <p className="mt-3 text-center text-xs text-text-secondary">
          Мгновенное подтверждение · 100% предоплата · бесплатная отмена за
          сутки до заезда
        </p>
      </div>
    </section>
  );
}

// Demo guest until the guest-facing auth exists; the backend requires the fields.
const GUEST = { name: "Гость", email: "guest@example.com", phone: "+79990000000" };

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDays(iso: string, delta: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}
