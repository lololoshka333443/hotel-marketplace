import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";

import { catalog } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function SearchPage() {
  useDocumentTitle("Поиск жилья");
  const [query, setQuery] = useState("");

  const { data: properties, isPending, isError } = useQuery({
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

      <div className="mt-6">
        <label
          htmlFor="search-query"
          className="block text-sm font-medium text-text-primary"
        >
          Поиск жилья
        </label>
        <input
          id="search-query"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Город, название…"
          className="mt-2 h-11 w-full rounded-button border border-border-strong bg-surface-card px-4 text-base text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-none focus-visible:shadow-focus-ring"
        />
      </div>

      {isPending ? (
        <p role="status" className="mt-12 text-text-secondary">
          Загружаем объекты…
        </p>
      ) : isError ? (
        <div className="mt-12 flex flex-wrap items-center gap-4">
          <p role="alert" className="text-feedback-error-text">
            Не удалось загрузить объекты. Обновите страницу.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Обновить страницу
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="mt-12 rounded-lg border border-border-default bg-surface-card p-8 text-center">
          <p className="text-base font-medium">Ничего не нашлось</p>
          <p className="mt-2 text-sm text-text-secondary">
            Попробуйте изменить запрос, например укажите другой город.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((property) => (
            <article
              key={property.id}
              className="flex flex-col overflow-hidden rounded-lg border border-border-default bg-surface-card"
            >
              {property.photos?.[0] ? (
                <img
                  src={property.photos[0]}
                  alt={property.name}
                  className="aspect-4/3 w-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div
                  aria-hidden="true"
                  className="flex aspect-4/3 w-full items-center justify-center bg-surface-sunken text-sm text-text-tertiary"
                >
                  Фото скоро появятся
                </div>
              )}
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
                  className="mt-4 inline-flex h-10 items-center justify-center rounded-button border border-border-strong text-sm font-medium text-text-primary transition-colors duration-150 hover:bg-interactive-hover"
                >
                  Подробнее
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
