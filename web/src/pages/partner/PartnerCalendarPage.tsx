import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { useState } from "react";
import { getToken, partner } from "@/api/client";
import { ChessBoard } from "@/components/ChessBoard";
import { IcalExport } from "@/components/IcalExport";
import { IcalImport } from "@/components/IcalImport";
import { ApiKeys } from "@/components/ApiKeys";
import { Webhooks } from "@/components/Webhooks";
import { RateManager } from "@/components/RateManager";
import { StopSellManager } from "@/components/StopSellManager";
import { UnitTypeManager } from "@/components/UnitTypeManager";
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
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Кабинет партнёра
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Шахматка
      </h1>
      <p className="mt-4 text-text-secondary">
        Доступность и цены по датам. Свободно / ждут оплаты / продано / закрыто.
      </p>

      {!first ? (
        <div className="mt-8 rounded-xl border border-border-default bg-surface-card p-8 text-center">
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
            <label className="block">
              <span className="mb-2 block text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
                Объект
              </span>
              <select
                value={activeId ?? undefined}
                onChange={(e) => setSelectedId(e.target.value)}
                className="h-size-control-field w-full rounded-lg border border-border-strong bg-surface-card px-4 text-base text-text-primary focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring"
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
          {activeId ? <UnitTypeManager propertyId={activeId} /> : null}
          {activeId ? <RatesForProperty propertyId={activeId} /> : null}
          {activeId ? <StopSellForProperty propertyId={activeId} /> : null}
        </div>
      )}

      <ApiKeys />
      <Webhooks />
    </div>
  );
}

/** Rates and stop sell are per unit type, so they need the property's rows. */
function RatesForProperty({ propertyId }: { propertyId: string }) {
  const { data: unitTypes } = useQuery({
    queryKey: ["unit-types", propertyId],
    queryFn: () => partner.listUnitTypes(propertyId),
  });
  if (!unitTypes || unitTypes.length === 0) return null;
  return <RateManager unitTypes={unitTypes} />;
}

function StopSellForProperty({ propertyId }: { propertyId: string }) {
  const { data: unitTypes } = useQuery({
    queryKey: ["unit-types", propertyId],
    queryFn: () => partner.listUnitTypes(propertyId),
  });
  if (!unitTypes || unitTypes.length === 0) return null;
  return <StopSellManager unitTypes={unitTypes} />;
}
