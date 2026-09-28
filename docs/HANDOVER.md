# Handover — контекст для нового чата

**Проект:** B2B2C маркетплейс бронирования жилья (отели, квартиры, апарты, комнаты).
Партнёры заводят объекты в нашем кабинете, гости бронируют и платят **у нас**,
комиссия с подтверждённой брони. Гео — Крым. Instant book, 100% предоплата,
отмена бесплатна за сутки до заезда.

**Source of truth — наша PostgreSQL.** Внешние площадки (Avito, Суточно.ру,
Яндекс, Airbnb) — каналы через адаптеры (Phase 2+), не главный календарь.
Double booking невозможен по архитектуре.

## Стек

- Бэк: Python 3.12, FastAPI, Uvicorn, asyncio
- PostgreSQL 16 + **asyncpg** (без ORM, чистый SQL), ручные `.sql` миграции
  (ранер `app/db/migrate.py`, состояние в `schema_migrations`)
- Redis (кэш доступности/цен), Pydantic v2, JWT, structlog, aiogram 3
- Фронт: React 18 + TS + Vite + Tailwind 4, Lucide-иконки, TanStack Query.
  **Single-app: FastAPI отдаёт собранную сборку** (не отдельный сервер)
- Деплой self-hosted; локально postgres@16 и redis через Homebrew запущены

## Что готово

**Бэкенд, Phase 1 (срезы 0–6), 52 теста — все зелёные:**

- 0 — skeleton, JWT (scopes partner/admin), healthz/readyz, пул asyncpg, рипер
- 1 — партнёр + property CRUD, публичный каталог (только published)
- 2 — генерация inventory_day на 730 дней, `GET /availability`, закрытие дат, unit-types
- 3 — **ядро бронирования**: `POST /bookings/hold`, SERIALIZABLE + `FOR UPDATE`
  по диапазону дат, hold TTL 15 мин, idempotency-key, рипер протухших hold.
  Тест: 20 параллельных hold на 1 номер → ровно 1 success
- 4 — оплата: `PaymentProvider` (stub/fail/tinkoff), hold→sold→confirmed
  одной транзакцией, refund
- 5 — rate plans, цены по дням (fallback на base_price), `GET /partner/calendar` (шахматка)
- 6 — правило отмены (24ч), комиссия (accrued/void), нотификации (email логируется
  + aiogram Telegram), `GET /v1/admin/reports/commission`

**Фронтенд (готов):**

- Лендинг, поиск, карточка объекта, checkout (выбор дат → наличие → посуточный
  прайс → hold → оплата), экран успеха
- Checkout: живой таймер до `hold_expires_at`, состояния «истекла»/«подтверждена»
- Шахматка партнёра: ряды — типы номеров, колонки — даты; состояния ячеек
  свободно/hold/продано/закрыто с иконкой+цветом (WCAG), залипающий заголовок
  строки, горизонтальный скролл, sr-only описание ячеек
- Кабинет партнёра: три состояния (нет объектов / один / много), login gate,
  модалка создания объекта. Пустое состояние объясняет ценность, один доминантный CTA
- Базовые компоненты: Button, Input, Badge, Modal
- Тёмная тема следует `prefers-color-scheme`
- Каталог и шахматка берут реальные данные из API (rate plan + сезонные цены
  показываются в шахматке корректно)

## Запуск

```bash
cd /Users/guuu/Desktop/hotel-marketplace
uv sync                                       # бэкенд-зависимости
uv run python -m app.db.migrate               # миграции (1..8)
uv run uvicorn app.main:app --port 8000       # API + собранный фронт на :8000
uv run pytest tests/ -q                       # 52 теста
uv run ruff check app tests && uv run ruff format app tests

cd web && npm run build                       # пересобрать фронт после правок
cd web && npx tsc -b --noEmit                 # проверка типов
```

БД: `hotel_mp`, юзер `hotel_user / hotel_pass`. `.env` создан из `.env.example`.
Сид-данные: демо-партнёр с объектами в Коктебеле (seed чинили — Pydantic
отвергает `.local` в email; перезапуск привязывает существующие объекты
к текущему партнёру).

## API (полный список, все под /v1)

auth: register, login, me
partner: properties (GET/POST/PATCH), unit-types (POST, GET by property),
inventory/generate, inventory/close, rate-plans (POST/GET), prices (POST),
calendar (GET)
public: properties (GET list/detail), availability
booking: hold (header Idempotency-Key), GET/{id}, cancel, pay, refund
admin: reports/commission
healthz, readyz

## Структура

```
hotel-marketplace/
├── migrations/0001..0008*.sql
├── app/modules/{auth,property,inventory,booking,payment,rate,admin,notification}/
├── app/{jobs/reaper.py, db/{pool,migrate}.py, config/{settings,legal,payment}.py}
├── web/src/{pages/{guest,partner}, components/ui, api/}
├── tests/   (pytest + pytest-asyncio)
└── docs/{ARCHITECTURE.md, LEGAL.md, HANDOVER.md}
```

## Что дальше (по плану)

1. **Phase 2:** iCal export (отдаём .ics), iCal import (read-only занятость),
   1 write-API адаптер канала, outbox + sync worker — *сделано*
2. **Phase 3:** двусторонний API-канал, webhooks, sync тарифов, reconciliation,
   retention доставки, лимит backlog, харденинг секретов — *сделано*
3. **Текущий шаг:** долги из `docs/handover/HANDOVER.md` — window.location.replace
   после логина, шардирование outbox
   — skip-link, переключатель тёмной темы, tertiary-токен палитры, лейбл
   поиска

## Нюансы, которые надо помнить

- Юр/налоги — `docs/LEGAL.md` (паркинг для юриста), в коде константы
  `app/config/legal.py`. Отвечаю только за технику
- Оплата — заглушка `PAYMENT_MODE=stub`; реальный эквайринг = реализация того
  же интерфейса `PaymentProvider`
- Часовой пояс Крыма — `Europe/Simferopol` (не Asia)
- Комиссия снапшотится при подтверждении; отчёты её не пересчитывают
- Пароль в auth — argon2id, как и API-ключи; старые SHA-256 строки
  доживают свой век и пере-хешируются при следующем входе. Секрет
  webhook-подписки опечатан (`WEBHOOK_SEAL_KEY`), без ключа доставка
  не подписывается
- Seed: перезапуск привязывает все объекты к текущему партнёру (фикс от
  предыдущей сессии)
