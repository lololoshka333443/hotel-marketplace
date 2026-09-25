import { useQuery } from "@tanstack/react-query";
import { Lock, ShoppingCart, Clock, Minus } from "lucide-react";

import { partner } from "@/api/client";
import type { CalendarDay, CalendarUnit } from "@/api/types";
import { cn } from "@/utils/cn";

/**
 * Partner chessboard: rows = unit types, columns = dates.
 * Cell state is never color-only - each carries an icon or a count, so the
 * board stays readable for color-blind users and in print.
 */
export function ChessBoard({ propertyId }: { propertyId: string }) {
  const { from, to } = defaultRange();

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["calendar", propertyId, from, to],
    queryFn: () => partner.calendar(propertyId, from, to),
    enabled: Boolean(propertyId),
  });

  if (isPending) {
    return <p className="py-8 text-text-secondary">Загружаем календарь…</p>;
  }
  if (isError) {
    return (
      <p className="py-8 text-feedback-error-text">
        Не удалось загрузить календарь.{" "}
        {error instanceof Error ? `(${error.message})` : ""}
      </p>
    );
  }

  const units = data?.units ?? [];
  if (units.length === 0) {
    return (
      <div className="rounded-lg border border-border-default bg-surface-card p-8">
        <p className="font-medium">Нет номеров для показа</p>
        <p className="mt-2 text-sm text-text-secondary">
          Добавьте тип номера к этому объекту, и здесь появится расписание.
        </p>
      </div>
    );
  }

  const dates = datesBetween(from, to);

  return (
    <div className="space-y-4">
      <Legend />
      <div className="overflow-hidden rounded-lg border border-border-default bg-surface-card">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Доступность по датам: строки - типы номеров, столбцы - даты
            </caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  className="sticky left-0 z-10 bg-surface-card px-3 py-2 text-left text-xs text-text-secondary shadow-[1px_0_0_var(--color-border-default)]"
                >
                  Номер
                </th>
                {dates.map((d) => (
                  <th
                    key={d.iso}
                    scope="col"
                    className="whitespace-nowrap px-2 py-2 text-center text-xs text-text-secondary"
                  >
                    <span className="block">{d.day}</span>
                    <span className="block font-mono text-text-tertiary">
                      {d.wd}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {units.map((unit: CalendarUnit) => (
                <tr key={unit.unit_type_id} className="border-t border-border-default">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-surface-card px-3 py-2 text-left font-medium shadow-[1px_0_0_var(--color-border-default)]"
                  >
                    <span className="block">{unit.unit_type_name}</span>
                    <span className="block text-xs font-normal text-text-tertiary">
                      всего {unit.total_units}
                    </span>
                  </th>
                  {unit.days.map((cell) => (
                    <Cell key={cell.date} cell={cell} total={unit.total_units} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Cell({ cell, total }: { cell: CalendarDay; total: number }) {
  const { free, closed, hold, sold } = cell;
  const state = closed ? "closed" : sold >= total ? "sold" : hold > 0 ? "hold" : "free";

  return (
    <td className="border-l border-border-default px-1 py-1 text-center">
      <span
        className={cn(
          "inline-flex size-9 items-center justify-center rounded-button text-xs font-medium",
          state === "free" && "bg-surface-sunken text-text-primary",
          state === "hold" && "bg-feedback-warning-bg text-feedback-warning-text",
          state === "sold" && "bg-feedback-info-bg text-feedback-info-text",
          state === "closed" && "bg-action-secondary text-text-tertiary",
        )}
        title={describe(cell, total)}
      >
        {state === "closed" ? (
          <Lock className="size-4" aria-hidden="true" />
        ) : state === "sold" ? (
          <ShoppingCart className="size-4" aria-hidden="true" />
        ) : state === "hold" ? (
          <Clock className="size-4" aria-hidden="true" />
        ) : free === 0 ? (
          <Minus className="size-4" aria-hidden="true" />
        ) : (
          free
        )}
      </span>
      <span className="sr-only">{describe(cell, total)}</span>
    </td>
  );
}

function describe(cell: CalendarDay, total: number): string {
  if (cell.closed) return `${cell.date}: даты закрыты для бронирования`;
  if (cell.sold >= total) return `${cell.date}: всё продано`;
  if (cell.hold > 0)
    return `${cell.date}: ${cell.hold} в холде, свободно ${cell.free}`;
  if (cell.free === 0) return `${cell.date}: нет мест`;
  return `${cell.date}: свободно ${cell.free}, цена ${cell.price.toFixed(0)} ₽`;
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-secondary">
      <Item swatch="bg-surface-sunken">Свободно (число)</Item>
      <Item swatch="bg-feedback-warning-bg">
        <Clock className="size-3.5" aria-hidden="true" /> В холде
      </Item>
      <Item swatch="bg-feedback-info-bg">
        <ShoppingCart className="size-3.5" aria-hidden="true" /> Продано
      </Item>
      <Item swatch="bg-action-secondary">
        <Lock className="size-3.5" aria-hidden="true" /> Закрыто
      </Item>
    </ul>
  );
}

function Item({
  swatch,
  children,
}: {
  swatch: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-2">
      <span
        className={cn(
          "inline-flex size-5 items-center justify-center rounded-button",
          swatch,
        )}
        aria-hidden="true"
      />
      {children}
    </li>
  );
}

/** 28 days starting today - the partner's default planning window. */
function defaultRange() {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + 28);
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  };
}

const WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];

function datesBetween(from: string, to: string) {
  const out: { iso: string; day: number; wd: string }[] = [];
  const d = new Date(from + "T00:00:00");
  const end = new Date(to + "T00:00:00");
  while (d < end) {
    out.push({
      iso: d.toISOString().slice(0, 10),
      day: d.getDate(),
      wd: WD[d.getDay()],
    });
    d.setDate(d.getDate() + 1);
  }
  return out;
}
