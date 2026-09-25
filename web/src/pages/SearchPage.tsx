import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";

import { catalog } from "@/api/client";

export function SearchPage() {
  const [query, setQuery] = useState("");

  const { data: properties, isPending, isError, error } = useQuery({
    queryKey: ["properties"],
    queryFn: ({ signal }) => catalog.list(undefined, signal),
  });

  const list = properties ?? [];
  const filtered = query
    ? list.filter(
        (p) =>
          p.name.toLowerCase().includes(query.toLowerCase()) ||
          p.city.toLowerCase().includes(query.toLowerCase()),
      )
    : list;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Поиск жилья</h1>
      <p className="mt-2 text-text-secondary">
        Крым · {filtered.length} объектов
      </p>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск: город, название…"
        aria-label="Поиск жилья"
        className="mt-6 h-11 w-full rounded-radius-button border border-border-default bg-surface-card px-4 text-base text-text-primary placeholder:text-text-tertiary focus:border-border-focus"
      />

      {isPending ? (
        <p className="mt-12 text-text-secondary">Загружаем объекты…</p>
      ) : isError ? (
        <p className="mt-12 text-feedback-error-text">
          Не удалось загрузить объекты.{" "}
          {error instanceof Error ? `(${error.message})` : ""}
        </p>
      ) : filtered.length === 0 ? (
        <div className="mt-12 rounded-radius-lg border border-border-default bg-surface-card p-8 text-center">
          <p className="text-base font-medium">Ничего не нашлось</p>
          <p className="mt-2 text-sm text-text-secondary">
            Попробуйте изменить запрос — например, другой город.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((property) => (
            <article
              key={property.id}
              className="flex flex-col overflow-hidden rounded-radius-lg border border-border-default bg-surface-card"
            >
              <img
                src={(property.photos?.[0] as string | undefined) ?? undefined}
                alt={property.name}
                className="aspect-4/3 w-full object-cover"
                loading="lazy"
              />
              <div className="flex flex-1 flex-col p-4">
                <p className="text-xs uppercase tracking-wide text-text-secondary">
                  {property.property_type}
                </p>
                <h2 className="mt-1 text-base font-semibold leading-snug">
                  {property.name}
                </h2>
                <p className="mt-2 text-sm text-text-secondary">
                  {property.city}
                </p>
                <Link
                  to={`/property/${property.id}`}
                  className="mt-4 inline-flex h-10 items-center justify-center rounded-radius-button border border-border-strong text-sm font-medium text-text-primary transition-colors duration-150 hover:bg-interactive-hover"
                >
                  Посмотреть объект
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
