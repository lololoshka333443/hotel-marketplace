import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { catalog } from "@/api/client";

export function HomePage() {
  const { data: properties, isPending, isError, error } = useQuery({
    queryKey: ["properties"],
    queryFn: ({ signal }) => catalog.list(undefined, signal),
  });

  return (
    <div>
      {/* hero */}
      <section className="relative isolate overflow-hidden">
        <img
          src="/rooms/3/photo_5298498534154293983_y.webp"
          alt="Вид на море и горы из номера в Коктебеле"
          className="absolute inset-0 -z-10 h-full w-full object-cover"
          loading="eager"
          fetchPriority="high"
        />
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-black/30 via-black/45 to-surface-page" />
        <div className="mx-auto flex min-h-[420px] max-w-7xl items-end px-4 py-16 sm:px-6 sm:py-24 lg:px-8">
          <div className="max-w-2xl">
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
          <p className="text-text-secondary">Загружаем объекты…</p>
        ) : isError ? (
          <p className="text-feedback-error-text">
            Не удалось загрузить объекты.{" "}
            {error instanceof Error ? `(${error.message})` : ""}
          </p>
        ) : properties.length === 0 ? (
          <p className="text-text-secondary">
            Пока нет опубликованных объектов - каталог появится, как партнёры
            добавят жильё.
          </p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2">
            {properties.map((property) => (
              <article
                key={property.id}
                className="overflow-hidden rounded-radius-lg border border-border-default bg-surface-card"
              >
                <img
                  src={(property.photos?.[0] as string | undefined) ?? undefined}
                  alt={property.name}
                  className="h-52 w-full object-cover"
                  loading="lazy"
                />
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
