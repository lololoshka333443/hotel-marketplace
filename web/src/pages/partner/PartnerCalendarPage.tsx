import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { useState } from "react";

import { getToken, partner } from "@/api/client";
import { ChessBoard } from "@/components/ChessBoard";
import { IcalExport } from "@/components/IcalExport";
import { IcalImport } from "@/components/IcalImport";
import { ApiKeys } from "@/components/ApiKeys";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PartnerCalendarPage() {
  useDocumentTitle("Шахматка - кабинет партнёра");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: properties } = useQuery({
    queryKey: ["partner-properties"],
    queryFn: () => partner.listProperties(),
    enabled: Boolean(getToken()),
  });

  const list = (properties ?? []) as { id: string; name: string }[];
  const first = list[0];
  const activeId = selectedId ?? first?.id ?? null;

  // The calendar is partner-only; /login sends back here on success.
  if (!getToken()) {
    return (
      <Navigate to="/login" state={{ from: "/partner/calendar" }} replace />
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Шахматка</h1>
      <p className="mt-2 text-text-secondary">
        Доступность и цены по датам. Свободно / ждут оплаты / продано / закрыто.
      </p>

      {!first ? (
        <div className="mt-8 rounded-lg border border-border-default bg-surface-card p-8 text-center">
          <p className="font-medium">У вас ещё нет объектов</p>
          <p className="mt-2 text-sm text-text-secondary">
            Добавьте объект, и здесь появится расписание по датам.
          </p>
          <Link to="/partner" className="mt-6 inline-block">
            <Button>Добавить объект</Button>
          </Link>
        </div>
      ) : (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between gap-4">
            <label className="text-sm">
              <span className="mb-1 block text-text-secondary">Объект</span>
              <select
                value={activeId ?? undefined}
                onChange={(e) => setSelectedId(e.target.value)}
                className="h-size-control-md rounded-button border border-border-strong bg-surface-card px-3 text-sm text-text-primary focus:border-border-focus focus:outline-none"
              >
                {list.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {activeId ? <ChessBoard propertyId={activeId} /> : null}
          {activeId ? <IcalExport propertyId={activeId} /> : null}
          {activeId ? <IcalImport propertyId={activeId} /> : null}
        </div>
      )}

      <ApiKeys />
    </div>
  );
}
