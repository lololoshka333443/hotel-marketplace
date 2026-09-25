import { useState } from "react";
import { Link } from "react-router-dom";

import { PROPERTIES } from "@/data/properties";

export function SearchPage() {
  const [query, setQuery] = useState("");

  const rooms = PROPERTIES.flatMap((property) =>
    property.rooms.map((room) => ({ ...room, propertyName: property.name })),
  );
  const filtered = query
    ? rooms.filter(
        (r) =>
          r.subtitle.toLowerCase().includes(query.toLowerCase()) ||
          r.propertyName.toLowerCase().includes(query.toLowerCase()),
      )
    : rooms;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Выберите свой номер</h1>
      <p className="mt-2 text-text-secondary">
        {PROPERTIES[0].city} · {filtered.length} номеров
      </p>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск: вид на море, терраса…"
        aria-label="Поиск номера"
        className="mt-6 h-11 w-full rounded-radius-button border border-border-default bg-surface-card px-4 text-base text-text-primary placeholder:text-text-tertiary focus:border-border-focus"
      />

      {filtered.length === 0 ? (
        <div className="mt-12 rounded-radius-lg border border-border-default bg-surface-card p-8 text-center">
          <p className="text-base font-medium">Ничего не нашлось</p>
          <p className="mt-2 text-sm text-text-secondary">
            Попробуйте изменить запрос — например, «море» или «терраса».
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((room) => (
            <article
              key={`${room.propertyName}-${room.title}`}
              className="group flex flex-col overflow-hidden rounded-radius-lg border border-border-default bg-surface-card"
            >
              <div className="relative">
                <img
                  src={room.cover}
                  alt={room.subtitle}
                  className="aspect-4/3 w-full object-cover transition-transform duration-200 group-hover:scale-105"
                  loading="lazy"
                />
                <span className="absolute left-3 top-3 inline-flex items-center rounded-full bg-surface-card/95 px-3 py-1 text-xs font-medium text-text-primary shadow-sm">
                  {room.badge}
                </span>
              </div>
              <div className="flex flex-1 flex-col p-4">
                <p className="text-xs text-text-secondary">{room.propertyName}</p>
                <h2 className="mt-1 text-base font-semibold leading-snug">
                  {room.subtitle}
                </h2>
                <p className="mt-2 text-sm text-text-secondary">
                  до {room.capacity} человек
                </p>
                <Link
                  to={`/property/${encodeURIComponent(room.title)}`}
                  className="mt-4 inline-flex h-10 items-center justify-center rounded-radius-button border border-border-strong text-sm font-medium text-text-primary transition-colors duration-150 hover:bg-interactive-hover"
                >
                  Посмотреть номер
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
