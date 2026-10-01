import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { useState } from "react";

import { catalog } from "@/api/client";
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
    queryFn: () => catalog.listUnitTypes(id as string),
    enabled: Boolean(id),
  });

  useDocumentTitle(property?.name);

  // Guests book a unit type; default to the first, switch via the selector.
  const [unitId, setUnitId] = useState<string | null>(null);
  const selectedUnit = unitTypes?.find((u) => u.id === unitId) ?? unitTypes?.[0];

  if (isPending) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-24 text-text-secondary sm:px-6 lg:px-8">
        <p role="status">Загружаем объект…</p>
      </div>
    );
  }

  if (isError || !property) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-24 sm:px-6 lg:px-8">
        <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
          Ошибка
        </p>
        <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
          Объект не найден
        </h1>
        <p className="mt-4 max-w-lg text-text-secondary">
          Возможно, он снят с публикации. Выберите другой объект из поиска.
        </p>
        <Link
          to="/search"
          className="mt-8 inline-flex h-size-control-lg items-center justify-center rounded-button bg-action-primary px-6 text-base font-medium text-text-on-action transition-colors duration-micro hover:bg-action-primary-hover focus-visible:shadow-focus-ring"
        >
          Вернуться к поиску
        </Link>
      </div>
    );
  }

  const photo = property.photos?.[0];

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-16 sm:px-6 lg:px-8">
      <div className="grid gap-12 lg:grid-cols-[1fr_360px]">
        <div>
          {photo ? (
            <img
              src={photo.full}
              alt={property.name}
              className="h-72 w-full rounded-xl object-cover sm:h-96"
            />
          ) : (
            <div className="flex h-72 w-full items-center justify-center rounded-xl border border-border-default bg-surface-sunken text-text-tertiary sm:h-96">
              Фото скоро появятся
            </div>
          )}

          <div className="mt-8">
            <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
              {property.property_type}
            </p>
            <h1 className="mt-3 font-serif text-4xl font-normal leading-display tracking-tight">
              {property.name}
            </h1>
            <p className="mt-4 text-text-secondary">
              {property.city} · заезд {property.checkin_time} · выезд{" "}
              {property.checkout_time}
            </p>
          </div>

          <section className="mt-12">
            <h2 className="font-serif text-2xl font-normal">Номера</h2>
            {!unitTypes || unitTypes.length === 0 ? (
              <p className="mt-4 text-text-secondary">
                В этом объекте пока нет номеров для бронирования. Загляните
                позже или выберите другой объект.
              </p>
            ) : (
              <ul className="mt-6 divide-y divide-border-default border-y border-border-default">
                {unitTypes.map((unit) => (
                  <li
                    key={unit.id}
                    className="flex items-center justify-between py-5"
                  >
                    <div>
                      <p className="font-medium">{unit.name}</p>
                      <p className="mt-1 text-sm text-text-secondary">
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
              <label className="block">
                <span className="mb-2 block text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
                  Номер
                </span>
                <select
                  value={selectedUnit.id}
                  onChange={(e) => setUnitId(e.target.value)}
                  className="h-size-control-field w-full rounded-lg border border-border-strong bg-surface-card px-4 text-base text-text-primary focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring"
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
