# Handover prompt: отель-маркетплейс, конец Phase 3

Вставь этот текст в начало нового чата, чтобы передать контекст.
Подробная история по срезам — в `docs/handover/HANDOVER-ical-export.md`.

---

Проект: B2B2C маркетплейс бронирования жилья (Крым, Коктебель).
Репо: `/Users/guuu/Desktop/hotel-marketplace` (git, ветка main, дерево чистое).

Стек: Python 3.12 + FastAPI + asyncpg + PostgreSQL 16 (бэк), React 18 +
TypeScript + Vite 6 + Tailwind 4 (фронт, single-app — бэк раздаёт `web/dist`).
PostgreSQL — источник правды, внешние площадки — каналы. Redis кэширует
доступность и хранит лимитеры.

## Состояние

- **Phase 1** — каталог, поиск, hold → оплата (stub) → confirm, кабинет
  партнёра (шахматка, цены, stop sell), уведомления.
- **Phase 2** — админка (модерация, отчёты по комиссии), iCal export/import,
  channel write-API.
- **Phase 3** — outbox + webhook-доставка, channel read-API тарифов и
  доступности, rate-limits, reconciliation-отчёт. **Phase 3 закрыта.**
- **147 тестов зелёные, 14 миграций, ruff/tsc/build чистые.**

## Инварианты, которые нельзя ломать

1. **Double booking невозможен**: hold внутри `SERIALIZABLE` + `FOR UPDATE` с
   упорядоченной блокировкой `(unit_type_id, date)`, `hold+sold <=
   total_units` в транзакции. **Любой write-путь (гость, канал) идёт через
   `create_hold` — обходов нет.**
2. **Событие и изменение неразделимы**: `outbox_service.emit()` вызывается
   строго внутри бизнес-транзакции. Откат = событие не родилось.
3. **Эмит никогда не ломает бизнес**: outbox глотает ошибки.
4. **Импорт не отменяет брони** и снимает только свои закрытия
   (`closed_source='import'` vs `'manual'`).
5. **Канал видит только своё**: ownership check по partner_id на каждом
   эндпойнте; чужое → 404. Канал не отменяет брони `origin='web'`.
6. **Троттлинг доставки — не ошибка**: `release_claim` без списания попытки.
7. **Лимитеры fail open** при падении Redis (лучше пропустить, чем уронить API).

## API-рельеф (что уже есть)

- Гость: каталог, `POST /v1/booking/hold`, checkout, `GET /availability`.
- Партнёр (JWT scope partner): properties, unit-types, chessboard calendar,
  rate plans + prices, inventory close/generate, api-keys, webhooks, iCal
  feed/import.
- Админ (scope admin): login, moderation, commission reports,
  `GET /v1/admin/outbox?status=`, `POST /v1/admin/outbox/{id}/retry`,
  `GET /v1/admin/outbox/metrics`, `GET /v1/admin/reconciliation`.
- Канал (X-API-Key): `POST /v1/channel/bookings`, `GET|POST
  /v1/channel/bookings/{id}[|/cancel]`, `GET /v1/channel/rates`,
  `GET /v1/channel/availability`. Те же лимиты: 120 чтений / 30 записей в
  минуту на ключ, 429 + `Retry-After`.
- Публичный iCal: `GET /v1/ical/{token}.ics`.

## Запуск и гейты

```
cd /Users/guuu/Desktop/hotel-marketplace
uv run python -m app.db.migrate            # 14 миграций
uv run python scripts/seed_demo.py         # partner + admin + 2 отеля
uv run uvicorn app.main:app --port 8000    # бэк + prod-фронт из web/dist
cd web && npm run dev                      # дев-фронт :5173, прокси /v1 → :8000
```

Гейты (все должны быть зелёные перед коммитом):
```
uv run pytest tests/ -q                    # 147
uv run ruff check app tests scripts
cd web && npx tsc -b --noEmit && npm run build
```

Демо-входы: партнёр `demo@example.com / demo-password`, админ
`admin@example.com / admin-password`. БД: hotel_mp (hotel_user / hotel_pass),
Redis на `localhost:6379/0`.

**Важно: тесты стирают дев-базу** (`committed_conn` делает `DELETE` по всем
таблицам в `hotel_mp`). После `pytest` — пересей `seed_demo.py`. Для CI
нужна отдельная БД (долг).

**Важно: при живых проверках поднимай сервер на свободном порту (например
8001)** — на 8000 может висеть другой проект; и обязательно гаси его перед
прогоном тестов, иначе воркер outbox'а будет мешаться в общей БД.

## Известные долги

- Регистрации на UI нет (бэк есть); гость-флоу захардкожен demo-гость в
  `BookingPanel.tsx`.
- В seed_demo нет подтверждённых броней — отчёт комиссии в демо показывает
  нули; iCal-фид пустой, пока не создать бронь.
- **Пароли и API-ключи — SHA-256 заглушки** → argon2 перед боем.
- **Секрет webhook-подписки хранится plaintext** → sealed column / vault.
- Нет rate-limit на backlog очереди; outbox не шардирован.
- `window.location.replace` после логина вместо инвалидации кеша TanStack.
- РЕДИЗАЙН отложен (меняется через `scripts/gen_palette.py` + `emit_tokens.py`,
  `theme.css` руками не править).

## Задача на следующий срез: retention для `webhook_delivery`

Таблица доставки растёт без ограничений: каждое событие × каждая подписка.
На неё опирается reconciliation, поэтому дропать старое нельзя — нужно хранить
сознательно.

Что сделать:
1. `migrations/0015__webhook_delivery_retention.sql` — партицирование
   `webhook_delivery` по `delivered_at` (помесячно). Retention: success-строки
   старше N дней (настройка в `settings.py`) удаляются, `status='failed'`
   хранить дольше — по ним сверяют проблемы.
2. Удаление по расписанию (джоба в `lifespan` или `scripts/`), не в запросе.
3. Сверка должна это пережить: статус `partial` уже есть (ledger прорежен) —
   проверить, что отчёт не ломается на свежей партиции.
4. Тесты: партиция создаётся, старые success удаляются, failed переживают
   retention, reconciliation всё ещё отвечает.

Не трогать: инварианты брони (SERIALIZABLE + FOR UPDATE), outbox-механику
(эмит/воркер/лимитеры), iCal.

Коммить по срезам, как принято: `feat(app):`, `feat(web):`, `test(app):`,
`docs:` — с мотивацией в теле.
