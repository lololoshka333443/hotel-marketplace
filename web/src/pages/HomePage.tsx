import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { catalog } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function HomePage() {
  useDocumentTitle();
  const { data: properties, isPending, isError } = useQuery({
    queryKey: ["properties"],
    queryFn: ({ signal }) => catalog.list(undefined, signal),
  });

  return (
    <div>
      {/* hero — the photo background went away with web/public/rooms; the
          redesign replaces this section. For now a brand-tinted gradient. */}
      <section className="relative isolate overflow-hidden bg-gradient-to-b from-action-primary/20 to-surface-page">
        {/* ds-allow-hardcode:start - hero min height: fixed editorial measure,
         * not part of the spacing scale. */}
        <div className="mx-auto flex min-h-[420px] max-w-7xl items-end px-4 py-16 sm:px-6 sm:py-24 lg:px-8">
          {/* ds-allow-hardcode:end */}
          <div className="max-w-2xl rounded-lg bg-scrim p-6 sm:p-8">
            <h1 className="text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl">
              Жильё в Крыму у моря
            </h1>
            <p className="mt-4 text-lg text-white/90">
              Отели, квартиры и апартаменты. Мгновенное подтверждение, 100%
              предоплата, бесплатная отмена за сутки до заезда.
            </p>
            <Link
              to="/search"
              className="mt-8 inline-flex h-12 items-center justify-center rounded-button bg-action-primary px-6 text-base font-semibold text-text-on-action transition-colors duration-150 hover:bg-action-primary-hover"
            >
              Найти жильё
            </Link>
          </div>
        </div>
      </section>

      {/* catalog - data from the API, never hardcoded */}
      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <h2 className="mb-6 text-2xl font-bold tracking-tight">Объекты</h2>

        {isPending ? (
          <p role="status" className="text-text-secondary">
            Загружаем объекты…
          </p>
        ) : isError ? (
          <div className="flex flex-wrap items-center gap-4">
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
        ) : properties.length === 0 ? (
          <p className="text-text-secondary">
            Пока нет опубликованных объектов. Каталог появится, как партнёры
            добавят жильё.
          </p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2">
            {properties.map((property) => (
              <article
                key={property.id}
                className="overflow-hidden rounded-lg border border-border-default bg-surface-card"
              >
                {property.photos?.[0] ? (
                  <img
                    src={property.photos[0]}
                    alt={property.name}
                    className="h-52 w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div
                    aria-hidden="true"
                    className="flex h-52 w-full items-center justify-center bg-surface-sunken text-sm text-text-tertiary"
                  >
                    Фото скоро появятся
                  </div>
                )}
                <div className="p-5">
                  <h3 className="text-lg font-semibold">{property.name}</h3>
                  <p className="mt-1 text-sm text-text-secondary">
                    {property.city || "Крым"}
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
      </section>
    </div>
  );
}
