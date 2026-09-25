import { Link } from "react-router-dom";

import { PROPERTIES } from "@/data/properties";

export function HomePage() {
  const totalRooms = PROPERTIES.reduce((sum, p) => sum + p.rooms.length, 0);

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
              Отдых в Коктебеле у моря
            </h1>
            <p className="mt-4 text-lg text-white/90">
              {PROPERTIES.length} отеля, {totalRooms} уютных номеров с видом на
              горы и море. Мгновенное подтверждение, бесплатная отмена за сутки
              до заезда.
            </p>
            <Link
              to="/search"
              className="mt-8 inline-flex h-12 items-center justify-center rounded-radius-button bg-action-primary px-6 text-base font-semibold text-text-on-action transition-colors duration-150 hover:bg-action-primary-hover"
            >
              Выбрать номер
            </Link>
          </div>
        </div>
      </section>

      {/* properties */}
      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <h2 className="mb-6 text-2xl font-bold tracking-tight">Наши отели</h2>
        <div className="grid gap-6 sm:grid-cols-2">
          {PROPERTIES.map((property) => (
            <article
              key={property.name}
              className="overflow-hidden rounded-radius-lg border border-border-default bg-surface-card"
            >
              <img
                src={property.rooms[0].cover}
                alt={property.name}
                className="h-52 w-full object-cover"
                loading="lazy"
              />
              <div className="p-5">
                <h3 className="text-lg font-semibold">{property.name}</h3>
                <p className="mt-1 text-sm text-text-secondary">
                  {property.address}
                </p>
                <p className="mt-3 text-sm text-text-secondary">
                  {property.rooms.length} номеров · парковка, Wi-Fi, барбекю,
                  батут для детей
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
