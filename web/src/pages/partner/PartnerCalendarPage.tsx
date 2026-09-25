import { useQuery } from "@tanstack/react-query";

import { partner } from "@/api/client";
import { ChessBoard } from "@/components/ChessBoard";
import { Button } from "@/components/ui/Button";

export function PartnerCalendarPage() {
  const { data: properties } = useQuery({
    queryKey: ["partner-properties"],
    queryFn: () => partner.listProperties(),
  });

  const list = (properties ?? []) as { id: string; name: string }[];
  const first = list[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Шахматка</h1>
      <p className="mt-2 text-text-secondary">
        Доступность и цены по датам. Свободно / в холде / продано / закрыто.
      </p>

      {!first ? (
        <div className="mt-8 rounded-lg border border-border-default bg-surface-card p-8 text-center">
          <p className="font-medium">У вас ещё нет объектов</p>
          <p className="mt-2 text-sm text-text-secondary">
            Добавьте объект, и здесь появится расписание по датам.
          </p>
          <Button className="mt-6">Добавить объект</Button>
        </div>
      ) : (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between gap-4">
            <label className="text-sm">
              <span className="sr-only">Объект</span>
              <select
                aria-label="Выберите объект"
                defaultValue={first.id}
                className="h-size-control-md rounded-button border border-border-default bg-surface-card px-3 text-sm text-text-primary focus:border-border-focus focus:outline-none"
              >
                {list.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ChessBoard propertyId={first.id} />
        </div>
      )}
    </div>
  );
}
