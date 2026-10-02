import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";

import { catalog } from "@/api/client";
import { formatPriceFrom } from "@/utils/format";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

/** Party sizes the catalog supports; a larger party narrows itself out. */
const GUEST_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8];

export function SearchPage() {
  useDocumentTitle("Поиск жилья");
  const [query, setQuery] = useState("");
  const [guests, setGuests] = useState<number>(0);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 6;

  // Debounce typing into the server-side query: a request per keystroke
  // races, and only the value the user paused on is wanted.
  const debouncedQuery = useDebouncedValue(query, 300);

  const {
    data: result,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["properties", guests, debouncedQuery, page],
    queryFn: ({ signal }) =>
      catalog.list(
        undefined,
        guests || undefined,
        debouncedQuery || undefined,
        PAGE_SIZE,
        page * PAGE_SIZE,
        signal,
      ),
  });

  const items = result?.items ?? [];
  const total = result?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  // A filter change must land on the first page of the new result set.
  function resetPage() {
    setPage(0);
  }

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-24 sm:px-6 lg:px-8">
      <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
        Крым
      </p>
      <h1 className="mt-4 font-serif text-4xl font-normal leading-display tracking-tight">
        Поиск жилья
      </h1>

      {/* One search pill on the page color — no boxed form chrome. */}
      <div className="mt-10 flex items-center gap-3 rounded-button border border-border-strong bg-surface-card p-2 pl-5">
        <label htmlFor="search-query" className="sr-only">
          Поиск жилья
        </label>
        <input
          id="search-query"
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            resetPage();
          }}
          placeholder="Город, название…"
          className="h-11 w-full bg-transparent text-base text-text-primary placeholder:text-text-tertiary focus:outline-none"
        />
        <span
          aria-hidden="true"
          className="h-8 w-px shrink-0 bg-border-strong"
        />
        <label
          htmlFor="search-guests"
          className="shrink-0 text-sm text-text-tertiary"
        >
          Гостей
        </label>
        <select
          id="search-guests"
          value={guests}
          onChange={(e) => {
            setGuests(Number(e.target.value));
            resetPage();
          }}
          className="h-11 shrink-0 appearance-none bg-transparent pr-2 text-base text-text-primary focus:outline-none"
        >
          <option value={0}>Любое</option>
          {GUEST_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <span className="shrink-0 text-sm text-text-tertiary">
          {total} объектов
        </span>
      </div>

      {isPending ? (
        <p role="status" className="mt-16 text-text-secondary">
          Загружаем объекты…
        </p>
      ) : isError ? (
        <div className="mt-16 flex flex-wrap items-center gap-4">
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
      ) : items.length === 0 ? (
        <div className="mt-16 rounded-xl border border-border-default bg-surface-card p-10 text-center">
          <p className="font-serif text-xl font-normal">Ничего не нашлось</p>
          <p className="mt-3 text-sm text-text-secondary">
            Попробуйте изменить запрос, например укажите другой город.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((property) => (
              <article
                key={property.id}
                className="flex flex-col overflow-hidden rounded-xl border border-border-default bg-surface-card transition-colors duration-micro hover:bg-interactive-hover"
              >
                {property.photos?.[0] ? (
                  <img
                    src={property.photos[0].thumb}
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
                <div className="flex flex-1 flex-col p-5">
                  <p className="text-xs font-medium uppercase tracking-eyebrow text-text-secondary">
                    {property.property_type}
                  </p>
                  <h2 className="mt-2 font-serif text-xl font-normal leading-tight text-text-primary">
                    {property.name}
                  </h2>
                  <p className="mt-2 text-sm text-text-secondary">
                    {property.city}
                  </p>
                  <p className="mt-2 text-sm text-text-secondary">
                    {property.min_price
                      ? formatPriceFrom(property.min_price, property.currency)
                      : "Цена не указана"}
                  </p>
                  <Link
                    to={`/property/${property.id}`}
                    className="mt-5 inline-flex w-fit items-center text-sm font-medium text-text-primary underline-offset-[3px] transition-colors duration-micro hover:underline"
                  >
                    Подробнее
                  </Link>
                </div>
              </article>
            ))}
          </div>
          {totalPages > 1 ? (
            <div className="mt-12 flex items-center justify-center gap-4">
              <Button
                variant="secondary"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Назад
              </Button>
              <span className="text-sm text-text-secondary">
                Страница {page + 1} из {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                Вперёд
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
