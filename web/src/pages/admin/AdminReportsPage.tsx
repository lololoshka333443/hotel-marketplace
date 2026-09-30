import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { admin } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Commission report: totals + per-partner breakdown over an optional range. */
export function AdminReportsPage() {
  useDocumentTitle("Отчёт по комиссии - админка");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState<{ from: string; to: string }>({
    from: "",
    to: "",
  });

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["admin-commission", applied.from, applied.to],
    queryFn: ({ signal }) =>
      admin.report(applied.from || null, applied.to || null, signal),
  });

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Админка
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Отчёт по комиссии
      </h1>
      <p className="mt-4 text-text-secondary">
        Комиссия снапшотится при подтверждении брони и не пересчитывается
        позже.
      </p>

      <form
        className="mt-6 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied({ from, to });
        }}
      >
        <Input
          label="Заезд от"
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
        />
        <Input
          label="Заезд до"
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          min={from || undefined}
        />
        <Button type="submit" variant="secondary" loading={isPending}>
          Применить фильтр
        </Button>
        {(applied.from || applied.to) && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setFrom("");
              setTo("");
              setApplied({ from: "", to: "" });
            }}
          >
            Сбросить
          </Button>
        )}
      </form>

      {isPending ? (
        <p role="status" className="mt-10 text-text-secondary">
          Загружаем отчёт…
        </p>
      ) : isError ? (
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <p role="alert" className="text-feedback-error-text">
            Не удалось загрузить отчёт. Обновите страницу.
          </p>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Попробовать снова
          </Button>
        </div>
      ) : data ? (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Stat label="Бронирований" value={String(data.total.bookings)} />
            <Stat label="Оборот" value={money(data.total.gross)} />
            <Stat label="Комиссия" value={money(data.total.commission)} />
          </div>

          <section className="mt-10">
            <h2 className="font-serif text-2xl font-normal">По партнёрам</h2>
            {data.partners.length === 0 ? (
              <p className="mt-4 rounded-xl border border-border-default bg-surface-card p-6 text-text-secondary">
                За выбранный период подтверждённых бронирований нет. Измените
                диапазон или вернитесь позже.
              </p>
            ) : (
              <div className="mt-4 overflow-x-auto rounded-xl border border-border-default">
                <table className="w-full border-collapse text-sm">
                  <caption className="sr-only">
                    Комиссия по партнёрам: почта, бронирования, оборот, комиссия
                  </caption>
                  <thead className="bg-surface-sunken text-left text-text-secondary">
                    <tr>
                      <Th>Партнёр</Th>
                      <Th align="right">Бронирований</Th>
                      <Th align="right">Оборот</Th>
                      <Th align="right">Комиссия</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.partners.map((p) => (
                      <tr
                        key={p.partner_id}
                        className="border-t border-border-default"
                      >
                        <Td>{p.partner_email}</Td>
                        <Td align="right">{p.bookings}</Td>
                        <Td align="right">{money(p.gross)}</Td>
                        <Td align="right">
                          <strong>{money(p.commission)}</strong>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

function money(v: number): string {
  return `${v.toLocaleString("ru-RU")} ₽`;
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-5">
      <p className="text-sm text-text-secondary">{label}</p>
      {/* The brief has no accent color, so the headline figure is set apart by
       * the serif face, not a hue. */}
      <p className="mt-2 font-serif text-3xl font-normal tracking-tight tabular-nums text-text-primary">
        {value}
      </p>
    </div>
  );
}

function Th({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right";
}) {
  return (
    <th
      scope="col"
      className={`px-4 py-2 font-medium ${align === "right" ? "text-right" : ""}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right";
}) {
  return (
    <td
      className={`px-4 py-3 text-text-primary ${
        align === "right" ? "text-right" : ""
      }`}
    >
      {children}
    </td>
  );
}
