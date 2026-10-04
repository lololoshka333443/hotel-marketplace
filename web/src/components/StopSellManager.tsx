import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock, Unlock } from "lucide-react";

import { partner } from "@/api/client";
import type { UnitTypeOut } from "@/api/types";
import { humanError } from "@/utils/errors";
import { plural } from "@/utils/plural";
import { daysBetween } from "@/utils/date";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/**
 * Stop sell: close a date range so nothing can be sold on it. Holds already
 * placed are refused (see create_hold), and the importer's closures are kept
 * apart from these by `closed_source`, so an iCal sync never silently reopens
 * a range the partner shut by hand.
 */
export function StopSellManager({ unitTypes }: { unitTypes: UnitTypeOut[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  const active = unitTypes.find((u) => u.id === selected) ?? unitTypes[0];

  if (unitTypes.length === 0) return null;

  return (
    <section className="mt-10">
      <h2 className="font-serif text-2xl font-normal">Стоп-селл</h2>
      <p className="mt-2 max-w-2xl text-sm text-text-secondary">
        Закрытые даты нельзя забронировать. iCal-импорт не отменяет закрытия,
        сделанные руками, и не снимает их.
      </p>

      <div className="mt-4">
        <label className="block">
          <span className="mb-2 block text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
            Номер
          </span>
          <select
            value={active?.id}
            onChange={(e) => setSelected(e.target.value)}
            className="h-size-control-field w-full rounded-lg border border-border-strong bg-surface-card px-4 text-base text-text-primary focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring"
          >
            {unitTypes.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {active ? <CloseForm unitType={active} /> : null}
    </section>
  );
}

function CloseForm({ unitType }: { unitType: UnitTypeOut }) {
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(addDays(today, 7));

  const nights = to > from ? daysBetween(from, to) : 0;
  const valid = nights >= 1;

  const close = useMutation({
    mutationFn: (closed: boolean) =>
      partner.inventory.close({
        unit_type_id: unitType.id,
        date_from: from,
        date_to: to,
        closed,
      }),
    onSuccess: (data, closed) => {
      // The chessboard's "closed" state and the guest's availability read both
      // come from inventory_day, and the outbox event is emitted by the
      // service — the UI only needs to repaint.
      void queryClient.invalidateQueries({
        queryKey: ["calendar", unitType.property_id],
      });
      setAffected({ closed, days: data.affected });
    },
  });

  const [affected, setAffected] = useState<{ closed: boolean; days: number } | null>(
    null,
  );

  return (
    <form
      className="mt-4 space-y-4 rounded-xl border border-border-default bg-surface-card p-5"
      onSubmit={(e) => {
        e.preventDefault();
        close.mutate(true);
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Заезд"
          type="date"
          value={from}
          min={today}
          onChange={(e) => setFrom(e.target.value)}
          required
        />
        <Input
          label="Выезд"
          type="date"
          value={to}
          min={addDays(from, 1)}
          onChange={(e) => setTo(e.target.value)}
          required
        />
      </div>
      {valid ? (
        <p className="text-sm text-text-secondary">
          Закроется {nights} {plural(nights, "день", "дня", "дней")}.
        </p>
      ) : (
        <p className="text-sm text-feedback-error-text">
          Выезд должен быть позже заезда.
        </p>
      )}
      {close.isError ? (
        <p role="alert" className="text-sm text-feedback-error-text">
          {humanError(close.error, "Не удалось закрыть даты. Попробуйте ещё раз.")}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" loading={close.isPending} disabled={!valid}>
          <Lock className="size-4" aria-hidden="true" />
          Закрыть даты
        </Button>
        <Button
          type="button"
          variant="secondary"
          loading={close.isPending && close.variables === false}
          disabled={!valid}
          onClick={() => close.mutate(false)}
        >
          <Unlock className="size-4" aria-hidden="true" />
          Открыть даты
        </Button>
        {affected ? (
          <p role="status" className="text-sm text-feedback-success-text">
            {affected.closed ? "Закрыто" : "Открыто"} {affected.days}{" "}
            {plural(affected.days, "день", "дня", "дней")}.
          </p>
        ) : null}
      </div>
    </form>
  );
}

function addDays(iso: string, delta: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

