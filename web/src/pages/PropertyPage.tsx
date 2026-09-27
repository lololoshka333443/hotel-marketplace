import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { useState } from "react";

import { catalog, partner } from "@/api/client";
import { BookingPanel } from "@/components/BookingPanel";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PropertyPage() {
  const { id } = useParams();

  const { data: property, isPending, isError } = useQuery({
    queryKey: ["property", id],
    queryFn: ({ signal }) => catalog.get(id as string, signal),
    enabled: Boolean(id),
  });

  // Unit types of this property - what guests actually book.
  const { data: unitTypes } = useQuery({
    queryKey: ["unit-types", id],
    queryFn: () => partner.listUnitTypes(id as string),
    enabled: Boolean(id),
  });

  useDocumentTitle(property?.name);

  // Guests book a unit type; default to the first, switch via the selector.
  const [unitId, setUnitId] = useState<string | null>(null);
  const selectedUnit = unitTypes?.find((u) => u.id === unitId) ?? unitTypes?.[0];

  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 text-text-secondary">
        <p role="status">Загружаем объект…</p>
      </div>
    );
  }

  if (isError || !property) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="text-2xl font-bold">Объект не найден</h1>
        <p className="mt-2 text-text-secondary">
          Возможно, он снят с публикации. Выберите другой объект из поиска.
        </p>
        <Link
          to="/search"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-button bg-action-primary px-5 text-sm font-semibold text-text-on-action transition-colors duration-150 hover:bg-action-primary-hover"
        >
          Вернуться к поиску
        </Link>
      </div>
    );
  }

  const photo = property.photos?.[0];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          {photo ? (
            <img
              src={photo}
              alt={property.name}
              className="h-72 w-full rounded-lg object-cover sm:h-96"
            />
          ) : (
            <div className="flex h-72 w-full items-center justify-center rounded-lg border border-border-default bg-surface-sunken text-text-tertiary sm:h-96">
              Фото скоро появятся
            </div>
          )}

          <div className="mt-6">
            <p className="text-xs uppercase tracking-wide text-text-secondary">
              {property.property_type}
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">
              {property.name}
            </h1>
            <p className="mt-2 text-text-secondary">
              {property.city} · заезд {property.checkin_time} · выезд{" "}
              {property.checkout_time}
            </p>
          </div>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Номера</h2>
            {!unitTypes || unitTypes.length === 0 ? (
              <p className="mt-3 text-text-secondary">
                В этом объекте пока нет номеров для бронирования. Загляните
                позже или выберите другой объект.
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-border-default rounded-lg border border-border-default bg-surface-card">
                {unitTypes.map((unit) => (
                  <li
                    key={unit.id}
                    className="flex items-center justify-between p-4"
                  >
                    <div>
                      <p className="font-medium">{unit.name}</p>
                      <p className="text-sm text-text-secondary">
                        до {unit.capacity} человек · {unit.total_units} в наличии
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="lg:sticky lg:top-6 lg:self-start">
          {unitTypes && unitTypes.length > 0 && selectedUnit ? (
            <>
              <label className="mb-3 block text-sm">
                <span className="mb-1 block text-text-secondary">Номер</span>
                <select
                  value={selectedUnit.id}
                  onChange={(e) => setUnitId(e.target.value)}
                  className="h-size-control-md w-full rounded-button border border-border-strong bg-surface-card px-3 text-sm text-text-primary focus:border-border-focus focus:outline-none"
                >
                  {unitTypes.map((unit) => (
                    <option key={unit.id} value={unit.id}>
                      {unit.name} · до {unit.capacity} человек
                    </option>
                  ))}
                </select>
              </label>
              <BookingPanel
                unitTypeId={selectedUnit.id}
                currency={property.currency}
              />
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
