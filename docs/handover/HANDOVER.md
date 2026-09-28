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
  доступности, rate-limits, reconciliation-отчёт, retention доставки, лимит на
  backlog очереди. **Phase 3 закрыта.**
- **162 теста зелёных, 16 миграций, ruff/tsc/build чистые.**

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
uv run python -m app.db.migrate            # 16 миграций
uv run python scripts/seed_demo.py         # partner + admin + 2 отеля
uv run uvicorn app.main:app --port 8000    # бэк + prod-фронт из web/dist
cd web && npm run dev                      # дев-фронт :5173, прокси /v1 → :8000
```

Гейты (все должны быть зелёные перед коммитом):
```
uv run pytest tests/ -q                    # 162
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
- Outbox не шардирован. Очередь теперь ограничена: при превышении глубины
  массовые события сбрасываются, бронирования идут вперёд; backlog остаётся
  только в глубину, а не в ширину.
- `window.location.replace` после логина вместо инвалидации кеша TanStack.
- РЕДИЗАЙН отложен (меняется через `scripts/gen_palette.py` + `emit_tokens.py`,
  `theme.css` руками не править).

## Что сделано в этом срезе: retention для `webhook_delivery`

Лог доставки рос без ограничений (каждое событие × каждая подписка), а на него
опирается reconciliation — дропать старое нельзя, старить сознательно.

- `migrations/0015__webhook_delivery_retention.sql` — `webhook_delivery` стала
  RANGE-партицированной по `delivered_at` (помесячно, `webhook_delivery_YYYYMM`)
  с DEFAULT-партицией; миграция переносит существующие строки.
- `app/modules/outbox/retention.py` — `retention_loop` в `lifespan` (рядом с
  reaper/outbox/poller): создаёт партиции на N месяцев вперёд, удаляет `success`
  старше `webhook_delivery_success_days` (30) и `failed` старше
  `webhook_delivery_failed_days` (365), дропает пустые партиции старше окна.
- `app/modules/outbox/service.py` — `record_delivery` переписана с
  `ON CONFLICT` на update-then-insert: уникальность пары теперь per-partition
  (глобальный индекс без ключа партицирования невозможен), FK ушли —
  партицированная таблица не может ссылаться наружу. Безопасность та же:
  claim через SKIP LOCKED, значит пару пишет только один воркер.
- Сверка переживает прореженный ledger: `delivered` деградирует до `partial`
  (часть доказательств стёрта) или `undelivered` (все) — те же статусы, что и у
  реально недошедшей доставки.

**Живые проверки**: бронь через channel-API → доставка в свежую партицию
(`tableoid` = текущий месяц), 200 записан; retention удалил успехи старше 30
дней, `failed` остался; reconciliation ответил `undelivered` для прореженного и
`failed` для мёртвого письма.

## Что сделано в этом срезе: лимит на backlog очереди

Очередь росла без ограничений: массовая операция (загрузка тарифов, iCal-импорт
сезона) кладёт тысячи событий, а воркер разгребает их на `webhook_rate_per_sec`
на подписку. Бронь — единственное событие, которое стоит денег, — ждала в конце.

- `migrations/0016__outbox_backlog_limit.sql` — `priority` в `outbox_event`
  (`1` для booking, `9` для массовых), индекс под упорядоченный claim,
  `outbox_shed_counter` — счётчик сброшенных событий (одна строка на тип, не
  вторая очередь).
- `app/modules/outbox/backlog.py` — глубина очереди (`pending`+`delivering`),
  решение `admit()` и запись в счётчик.
- `service.emit()` — бронь эмитится всегда при любой глубине; массовое событие
  сверх `outbox_max_pending` (2000) сбрасывается: считается и логируется, а не
  встаёт в очередь. Сброс безопасен — канал вытягивает тарифы и доступность
  через read-API.
- `claim_due` — `ORDER BY priority, next_attempt_at, happened_at`; RETURNING
  переупорядочивается в Python, потому что UPDATE пересканирует таблицу и
  возвращает строки в своём порядке.
- `queue_metrics` — `depth_limit`, `lag_alert_sec`, `shed_total`: пороги
  показывает бэк, чтобы UI рисовал одну линию, а не угадывал.
- Фронт: полоса метрик показывает «В очереди N / лимит», «Сброшено лимитом» и
  два алерта — «достигнут лимит, идёт shedding» и «очередь отстаёт».

**Живые проверки**: 2600 изменений цен при задушенной подписке → глубина
встала на 2000, 600 событий сброшено и посчитаны; бронь через channel-API при
переполненной очереди доставлена (200, `published`), пока ~1860 rate-событий
ещё ждали.

## Задача на следующий срез: закрыть долги безопасности

Пароли партнёров, API-ключи каналов и секреты webhook-подписок — SHA-256 или
plaintext. До боевого подключения каналов это нужно закрыть: утекший ключ даёт
бронировать за чужой счёт, утекший секрет — подделывать наши вебхуки.

Что сделать:
1. `migrations/0017__secrets.sql` — argon2id для паролей и API-ключей
   (`password_hash`/`api_key_hash`), sealed-колонка для секретов подписок
   (AEAD с ключом из настроек, ротация — отдельный долг).
2. Верификация: старые SHA-256 хеши распознаются и пере-хешируются при
   ближайшем логине/использовании ключа — без forced reset всех партнёров.
3. Секрет подписки: при выдаче показывается один раз (как API-ключ), в БД
   хранится запечатанным.
4. Тесты: вход по старому паролю + пере-хеш; ключ работает; секрет не виден в
   `GET /partner/webhooks`; подделанная подпись отклоняется получателем.
5. Документ: убрать пункты из «Известные долги».

Не трогать: инварианты брони (SERIALIZABLE + FOR UPDATE), outbox-механику
(эмит/воркер/лимитеры — shedding и приоритет уже на месте), iCal, retention.
