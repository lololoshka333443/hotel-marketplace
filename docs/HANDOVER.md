# Handover — контекст для нового чата

**Проект:** B2B2C маркетплейс бронирования жилья (отели, квартиры, апарты, комнаты).
Партнёры заводят объекты в нашем кабинете, гости бронируют и платят **у нас**,
мы берём комиссию с подтверждённой брони. Гео старта — Крым. Instant book,
100% предоплата, отмена бесплатна за сутки до заезда.

**Ключевое:** source of truth — наша PostgreSQL. Внешние площадки (Avito,
Суточно.ру, Яндекс, Airbnb) — это каналы, подключаемые адаптерами (Phase 2+),
а не главный календарь. Double booking невозможен по архитектуре.

## Стек

- Python 3.12, FastAPI, Uvicorn, asyncio
- PostgreSQL 16 + **asyncpg** (без ORM, чистый SQL), ручные `.sql` миграции
  (ранер `app/db/migrate.py`, трекается в `schema_migrations`)
- Redis (кэш доступности/цен), Pydantic v2, JWT, structlog, sentry-sdk
- aiogram 3 (Telegram-бот партнёра), httpx (будут каналы)
- Фронт: React 18 + TypeScript + Vite + Tailwind 4 (НЕ НАЧИНАЛИ)
- Деплой: self-hosted; локально всё на Homebrew (postgres@16, redis запущены)

## Что готово (Phase 1, срезы 0–6)

| Срез | Содержание |
|---|---|
| 0 | skeleton, JWT-авторизация (scopes partner/admin), healthz/readyz, пул asyncpg, рипер |
| 1 | партнёр + property CRUD, публичный каталог (только published) |
| 2 | генерация inventory_day на 730 дней, `GET /availability`, закрытие дат, unit-types |
| 3 | **ядро бронирования**: `POST /bookings/hold` — SERIALIZABLE + `FOR UPDATE` по диапазону, hold TTL 15 мин, idempotency-key, рипер протухших hold |
| 4 | оплата: `PaymentProvider` (stub/fail/tinkoff), hold→sold→confirmed одной транзакцией, refund |
| 5 | rate plans, цены по дням (с fallback на base_price), `GET /partner/calendar` (шахматка) |
| 6 | правило отмены (24ч), комиссия (accrued/void), нотификации, `GET /v1/admin/reports/commission` |

**Тестов: 52, все зелёные.** Включая 20 параллельных hold на 1 номер → ровно 1 success.

## Структура

```
hotel-marketplace/
├── migrations/0001..0008*.sql
├── app/
│   ├── main.py              # FastAPI factory, lifespan, роутеры
│   ├── config/{settings,legal,payment}.py
│   ├── db/{pool,migrate}.py
│   ├── modules/{auth,property,inventory,booking,payment,rate,admin,notification}/
│   ├── jobs/reaper.py
│   └── utils/{logger,redis}.py
├── tests/                   # pytest + pytest-asyncio
├── docs/{ARCHITECTURE.md,LEGAL.md}
```

## Запуск

```bash
cd /Users/guuu/Desktop/hotel-marketplace
uv sync
uv run python -m app.db.migrate   # применить миграции
uv run uvicorn app.main:app --port 8000   # http://localhost:8000/docs
uv run pytest tests/ -q            # 52 теста
uv run ruff check app tests && uv run ruff format app tests
```

БД: `hotel_mp`, юзер `hotel_user / hotel_pass`, .env уже создан из .env.example.

## Что дальше

1. **Фронтенд** (React + Vite): лендинг/поиск, карточка объекта, checkout
   (hold → pay), кабинет партнёра (шахматка на grid-таблице), админка.
   У меня есть дизайн-промты — я скину, когда дойдём до дизайна.
2. **Phase 2**: iCal export (мы отдаём .ics), iCal import (read-only занятость),
   1 write-API адаптер канала, outbox + sync worker.
3. **Phase 3**: двусторонний API-канал, webhooks, sync тарифов, reconciliation.

## Важные нюансы

- Закон/налоги — вынесены в `docs/LEGAL.md` (паркинг для юриста), в коде это
  константы в `app/config/legal.py`. Я отвечаю только за технику.
- Оплата сейчас — заглушка `PAYMENT_MODE=stub`. Реальный эквайринг —
  реализация того же интерфейса, когда юрчасть будет закрыта.
- Часовой пояс Крыма — `Europe/Simferopol` (не Asia).
- Комиссия снапшотится при подтверждении; отчёты её не пересчитывают.
- Пароль в auth — SHA-256 заглушка, заменить на bcrypt/argon2 перед боем.
