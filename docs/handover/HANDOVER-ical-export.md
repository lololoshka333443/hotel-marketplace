# Handover prompt: UX-тексты + логин + a11y + админка + iCal + write-API + outbox + read-API + rate limits + reconciliation

Вставь этот текст в начало нового чата, чтобы передать контекст.

---

Проект: B2B2C маркетплейс бронирования жилья (Крым, Коктебель). Стек: Python 3.12
+ FastAPI + asyncpg + PostgreSQL 16 (бэк), React 18 + TypeScript + Vite 6 +
Tailwind 4 (фронт, single-app). Исходник правды — наша PostgreSQL; внешние
площадки — каналы. Phase 2 готова целиком (админка, iCal export/import,
channel write-API); Phase 3: outbox + webhook-доставка, channel read-API
тарифов/доступности, rate-limits, reconciliation-отчёт, retention доставки, лимит на backlog очереди (162 теста). Подробности — docs/ARCHITECTURE.md и README.

## Что сделано в этой сессии

### 1. UX-тексты (фронт)
По ux-writing/SKILL.md: errors = what → why → how, empty states = value →
action, verb+object на кнопках, no raw error codes, payment-stub обозначен.

### 2. Страницы логина
`/login` (партнёр) и `/admin/login` (стафф) — отдельные роуты с возвратом через
`location.state.from`. Один token store; scope решает эндпойнт выдачи.

### 3. Дизайн-ревью + a11y-аудит
Отчёт: `docs/handover/AUDIT-design-a11y.md`. Исправлены 4 контрастных провала,
title страниц (`hooks/useDocumentTitle.ts`), live-регионы, scrim в герое.

### 4. Админка (бэк + фронт)
- `migrations/0010__admin.sql` — таблица `admin`.
- `POST /v1/admin/login` (scope: admin), `GET /v1/admin/properties?status=`
  (очередь модерации), `PATCH /v1/admin/properties/{id}/status` (конечный
  автомат; нелегальные переходы → 409).
- Фронт: `web/src/pages/admin/` — отчёт по комиссии с фильтром дат + модерация.
- Партнёр может публиковать сам (протестировано); админ — надзор: approve /
  reject / block / unblock.

### 5. iCal export (Phase 2, срез 1)

Pull-based фид по типу номера: токен в URL — единственный credential.

- `migrations/0011__ical.sql` — `ical_feed` (один фид на unit_type, токен
  уникален, `enabled` флаг).
- `app/modules/sync/ical_export.py` — генерация RFC 5545: confirmed/paid →
  `STATUS:CONFIRMED`, hold → `STATUS:TENTATIVE`, закрытые диапазы (stop sell)
  одним событием через gaps-and-islands. DTEND эксклюзивный (checkout).
  Прошлые брони не экспортируются. UID стабилен (`booking:{id}`,
  `closed:{ut}:{date}`), чтобы канал мог обновлять/отменять события.
- `app/modules/sync/routes.py`:
  - `GET /v1/ical/{token}.ics` — публичный, `text/calendar`, `Cache-Control:
    no-store`; unknown/disabled → 404;
  - `GET /v1/partner/unit-types/{id}/ical-feed` — текущий фид;
  - `POST /v1/partner/unit-types/{id}/ical-feed` — создать / ротировать токен
    (старая ссылка умирает сразу; ownership check по partner_id).
- Фронт: `components/IcalExport.tsx` на странице шахматки — URL в readonly-инпуте,
  «Копировать», «Обновить ссылку» с confirm-модалкой (кнопка повторяет действие),
  «Создать ссылку» для отсутствующего фида.
- `settings.app_base_url` — публичный origin для ссылок (в локальном `.env`
  это `http://localhost:8002`, в проде выставить реальный домен).

### 6. iCal import (Phase 2, срез 2)

Pull-based импорт: партнёр указывает внешний ical-URL, блокировки из него
становятся stop sell у нас.

- `migrations/0012__ical_import.sql` — `ical_subscription` (одна подписка на
  unit_type, `UNIQUE (unit_type_id)`) + `inventory_day.closed_source`
  (`'manual'` | `'import'`).
- `app/modules/sync/ical_parser.py` — свой мини-парсер RFC 5545: unfolding,
  DTSTART/DTEND (date и datetime-форма), UID/SUMMARY, подмножество RRULE
  (FREQ/INTERVAL/COUNT/UNTIL). **Неподдержимое не игнорируется тихо** —
  unbounded RRULE без COUNT/UNTIL и экзотика → `IcalParseError`, синхронизация
  уходит в `last_status='error'`, а не импортирует кривую доступность.
- `app/modules/sync/ical_import.py` — ядро. Сетевым fetch вне транзакции;
  `apply_import` идемпотентен: закрывает даты из фида (`closed_source='import'`),
  **снимает только то, что закрыло само** (ручные stop sell партнёра живут),
  добивает строки inventory на горизонте, если фид заблокировал то, до чего
  генератор ещё не дошёл.
- `app/modules/sync/poller.py` — фоновый цикл по образцу reaper'а;
  `list_due` атомарно клеймит строки `FOR UPDATE SKIP LOCKED` (lock не держится
  через сетевой fetch). Стартует в `lifespan` рядом с reaper'ом.
- `app/modules/sync/routes.py` (импортная часть): `GET/PUT/DELETE
  /v1/partner/unit-types/{id}/ical-import` + `POST .../ical-import/sync`
  (sync right now, без ожидания поллера). Ownership check по partner_id.
- Фронт: `components/IcalImport.tsx` на странице шахматки под экспортом —
  инпут URL, статус последней синхронизации (ok/pending/error), «Синхронизировать
  сейчас», «Отключить импорт» с confirm-модалкой.

#### Инварианты, которые проверены и живьём, и тестами
1. **Импорт не отменяет оплаченные брони.** Бронь на дате, которую закрыл
   импорт, остаётся `confirmed`; `create_hold` на закрытую дату отдаёт 409
   «dates closed (stop sell) at …». Внешний фид не властен над реальными
   деньгами.
2. **Импорт снимает только своё.** Ручное закрытие партнёра (`closed_source=
   'manual'`) переживает любую синхронизацию.
3. **Кольцо export→import работает на наших же данных**: закрыл диапазон на
   одном типе номера → экспорт отдал одно VEVENT → импорт закрыл 4 даты в
   другом типе номера с правильным source → открыл обратно → `cleared:4`.

#### Баг, пойманный при живой проверке (исправлен)
`apply_import` считал разблокированные даты через `fetchval` на
`UPDATE ... RETURNING 1` — это отдаёт только первую строку, и при очистке
диапазона счётчик показывал `1` вместо реальных N. Заменено на `fetch` +
`len(rows)`, тест усилен (теперь закрывает импортом 2 даты и требует
`cleared == 2`). Аналогичная ловушка может ждать любой `... RETURNING` через
`fetchval` — проверь при ревью.

### 7. Channel write-API (Phase 2, срез 3 — завершающий)

Канал (площадка/менеджер каналов) толкает брони в нас через API-ключ вместо
JWT. Ключ — partner-scoped секрет, видит только своё имущество.

- `migrations/0013__channel_api_key.sql` — `api_key`: хранится только
  SHA-256 (как пароли, до перехода на argon2), `key_prefix` — видимый палец
  для UI, `enabled`, `last_used_at`.
- `app/modules/channel/service.py`:
  - `create_key` — plaintext отдаётся **один раз**, больше нигде не хранится и
    не показывается;
  - `resolve_key` — маппинг ключа → partner; отвергает неизвестный,
    отключённый и неактивный партнёра; метит `last_used_at`;
  - `create_channel_booking` — **тот же путь, что у гостя**:
    `create_hold` (SERIALIZABLE + FOR UPDATE, origin='channel') →
    `pay_and_confirm`. Никаких обходов инвентаря;
  - `idempotency_namespace` — ключи канала живут в своём пространстве
    (`channel:{partner_id}:{client_key}`), не пересекаются с веб-ключами;
  - replay уже подтверждённой брони возвращает её как успех (канал
    переспросил после нашего confirm), а не 409.
- `app/modules/channel/routes.py`:
  - `POST /v1/channel/bookings` (X-API-Key) — пуш брони;
  - `GET /v1/channel/bookings/{id}` — только channel-origin брони свои;
  - `POST /v1/channel/bookings/{id}/cancel` — hold → release, confirmed →
    refund;
  - `GET/POST /v1/partner/api-keys`, `DELETE /v1/partner/api-keys/{id}` —
    управление ключами партнёром (JWT).
- `create_hold` научился `origin` (по умолчанию 'web'), чтобы канал
  маркировался в БД и отчётах.
- Фронт: `components/ApiKeys.tsx` на странице шахматки — список ключей
  (prefix + «использован»), создание с модалкой «ключ показан один раз»,
  отзыв через confirm.

#### Инварианты, проверенные и живьём, и тестами
1. **Тот же путь, что у гостя** — канал не может обойти stop sell (409),
   перебронировать занятое (409) или создать бронь мимо inventory.
2. **Изоляция партнёров** — ключом demo чужой unit type → 404; свой → 201.
3. **Идемпотентность end-to-end** — replay отдаёт ту же подтверждённую бронь,
   второй записи нет. Другие даты с тем же ключом → 409 conflict.
4. **Отзыв** — после DELETE ключ даёт 401; созданные им брони остаются.
5. **Канал не отменяет чужое** — бронь, созданную гостем напрямую (origin
   'web'), канал отменить не может.

### 8. Outbox + webhook-доставка (Phase 3, срез 1)

Мы → внешние системы. Любое бизнес-событие пишется в `outbox_event` **в той же
транзакции**, что и изменение, которое его описывает; фоновый воркер забирает
строки и доставляет по подпискам партнёра. Запрос никогда не ждёт webhook —
медленный или мёртвый получатель не тормозит бронь.

- `migrations/0014__outbox.sql` — три таблицы: `outbox_event` (событие с
  состояниями pending/delivering/published/failed, backoff, dead-letter),
  `webhook_subscription` (URL + секрет + фильтр по типам событий),
  `webhook_delivery` (лог доставки каждому получателю — это и есть
  reconciliation).
- `app/modules/outbox/service.py` — `emit()` на запись (глотает ошибки, чтобы
  никогда не откатить бизнес-операцию), `claim_due` (SKIP LOCKED, как у
  reaper'а и iCal-импортёра), `reclaim_stale` (воркер умер mid-flight →
  строка вернётся в очередь), dead-letter при `attempts >= max_attempts`.
- `app/modules/outbox/deliver.py` — HTTP POST, тело подписывается
  HMAC-SHA256 (`X-Signature`), `Idempotency-Key` = id события (получатель
  может получить его дважды при ретрае — должен дедуплицить).
- `app/modules/outbox/worker.py` — вечный цикл рядом с reaper и поллером.
- Точки эмита (всё внутри бизнес-транзакции): `booking.confirmed`,
  `booking.cancelled` (refund + истёкший hold), `rate.prices_changed`,
  `inventory.availability_changed` (ручной стоп-селл + iCal-импорт),
  `property.status_changed` (модерация).
- Роуты: партнёр `GET/POST/DELETE /v1/partner/webhooks` (секрет не
  возвращается), админ `GET /v1/admin/outbox?status=` + `POST
  /v1/admin/outbox/{id}/retry` (поднятие дед-леттера).
- Фронт: `components/Webhooks.tsx` на шахматке (подписка с выбором событий,
  статус последней доставки) и `pages/admin/AdminOutboxPage.tsx` —
  reconciliation-вьюер с фильтром по статусу и кнопкой «Повторить».

#### Инварианты, проверенные и тестами, и живьём
1. **Событие и изменение неразделимы** — откат транзакции убивает и событие
   (тест на rollback).
2. **Эмит никогда не ломает бизнес** — сломанный outbox глотает ошибку, бронь
   проходит.
3. **Частичный успех не блокирует** — один отвалившийся webhook не мешает
   другому получить событие; ретрай доходит только до тех, кто не ответил 200.
4. **Dead letter** — 6 попыток с экспоненциальным бэкоффом → `failed` с
   понятной ошибкой, админ может поставить обратно в очередь.
5. **Подпись проверяется на приёмной стороне** — поднимал локальный hook:
   `sig_ok: true` на каждом событии.

### 9. Channel read-API тарифов и доступности (Phase 3, срез 2)

Канал читает тарифы и доступность **тем же API-ключом**, которым толкает
брони. Это закрывает кольцо sync'а: `rate.prices_changed` / 
`inventory.availability_changed` прилетают в webhook → канал идёт читать
диапазон из события.

- `app/modules/channel/service.py`:
  - `get_channel_rates` — цены по дням над полузакрытым диапазоном
    `[date_from, date_to)` с тем же fallback на `unit_type.base_price`, что
    использует `rate/service.py:get_prices` партнёрский кабинет;
  - `get_channel_availability` — `free = available - hold - sold` (floored),
    закрытые даты (`inventory_day.closed` **или** `price_day.stop_sell`)
    помечены отдельно и `bookable = 0`: канал не должен продавать закрытое,
    это же отбивает write-API;
  - обе функции — ownership check через существующий `unit_type_owned_by`
    (→ `NotOwned` → 404), диапазон ограничен 92 днями как календарь (`BadRange`
    → 422);
  - активный rate plan один на unit_type (`active` + `ORDER BY created_at
    LIMIT 1` в LATERAL) — без плана всё работает на base_price.
- `app/modules/channel/routes.py`:
  - `GET /v1/channel/rates?unit_type_id=&date_from=&date_to=` (X-API-Key);
  - `GET /v1/channel/availability?...` (X-API-Key);
  - ключам используется тот же `resolve_key`, что и для брони: `last_used_at`
    метится и на чтение (утечку ключа хоть как-то видно).
- Фронт: в `components/Webhooks.tsx` подписана dokumentация — канал читает
  тарифы/доступность тем же ключом; эндпойнты прописаны рядом с подписками.

#### Инварианты, проверенные и тестами, и живьём
1. **Изоляция партнёров** — ключом demo чужой unit type → 404 на обоих
   эндпойнтах (и в сервисных тестах через `NotOwned`, и в HTTP через
   TestClient); свой → 200.
2. **Цены сходятся** — то, что партнёр выставил через `/v1/partner/prices`,
   канал и читает; проверено в том числе крестом против
   `rate.service.get_prices`. Fallback на base_price — и с rate plan, и без
   него.
3. **Закрытая дата помечена** — stop sell руками и `price_day.stop_sell`
   дают `closed: true, bookable: 0` (free при этом может быть > 0 — это
   инвентарь, а не разрешение продавать).
4. **Ключи** — нет ключа / неизвестный ключ → 401; пустой или слишком
   длинный диапазон → 422.
5. **Живьём** (поднимал на :8001): создал тариф 7770 на 3 ночи + закрыл
   дату партнёром → канал прочитал 7770/6500-base и `closed` на нужных
   днях; чужой тип номера → 404.

### 10. Rate limits + метрики очереди (Phase 3, срез 3)

Канал больше не может нас расшатать, а мы — вебхук партнёра. Оба ограничены
fixed-window лимитами в Redis.

- `app/utils/ratelimit.py` — `acquire(key, limit, window_sec)`: INCR + EXPIRE
  одним Lua-вызовом (счётчик точен при конкурентном доступе). **Если Redis
  недоступен — fail open**: сломанный лимитер не должен ронять API; пропуск
  логируется.
- Channel API (`app/modules/channel/routes.py`): раздельные бакеты на чтение и
  запись (`channel_read_limit_per_min` / `channel_write_limit_per_min`, окно
  `rate_limit_window_sec`). Превышение → **429 + `Retry-After`**. Чтение
  тарифов не тратит бюджет на бронирование; 401 (плохой ключ) не тратит
  ничего — лимит считается после резолва ключа.
- Доставка (`app/modules/outbox/worker.py`): лимит на подписку
  (`webhook_rate_per_sec`). Троттленное событие возвращается в очередь новым
  `release_claim` **без списания попытки** — лимит это не ошибка, и
  dead-letter на него не положен.
- `GET /v1/admin/outbox/metrics` — глубина очереди, в доставке, ждут ретрая,
  dead letters, медианная задержка (`percentile_cont(0.5)` за последний час),
  возраст самого старого pending. Фронт: полоса метрик в
  `pages/admin/AdminOutboxPage.tsx`, рефреш 15s.
- Все лимиты — в `settings.py` из env, чтобы тестам не спать по минуте.

#### Инварианты, проверенные и тестами, и живьём
1. **Сверх лимита — 429**, не 500 и не тихий успех, с осмысленным
   `Retry-After` (в пределах окна). Под лимитом поведение не изменилось.
2. **Бакеты разделены** — чтения исчерпали read-бакет (429), но бронь прошла
   (201).
3. **Окно прошло — бюджет вернулся** (тест пересекает границу окна).
4. **Троттлинг не сжигает попытки** — событие возвращается в очередь, attempts
   не растёт; после освобождения ключа уходит в нормальный ретрай.
5. **401 главнее 429** — запросы с плохим ключом ничего не тратят.
6. **Живьём** (поднимал на :8001 с заниженными лимитами): 5 чтений при лимите 3
   → 200×3, 429×2 (`Retry-After=60`); 3 брони при лимите 2 → 201×2, 429;
   насыщенный redis-ключ подписчика → `outbox-throttled` в логе, событие в
   `pending`, 0 строк `webhook_delivery`; ключ освободился → пошёл ретрай.

### 11. Reconciliation-отчёт (Phase 3, срез 4)

Метрики очереди показывают, *сколько* событий торчит; сверка показывает,
*какая именно* бронь не дошла до канала. Это отчёт, который открывают, когда
партнёр говорит «мы не получали эту бронь».

- `GET /v1/admin/reconciliation?date_from=&date_to=` (`outbox/service.py:
  reconciliation`) — каждая бронь с `origin='channel'` против её последнего
  события `booking.*` (подтверждение / отмена) с подсчётом ожидаемых и
  доставленных подписок.
- Статусы доставки: `delivered` / `queued` / `failed` (dead-letter) /
  `undelivered` / `partial` (ledger прорежен retention'ом) / `no_listener`.
  **Отсутствующий вебхук — это `no_listener`, не ошибка** — партнёр просто не
  настроил или выключил хук.
- Правило «ожидаемых»: подписка включена, подписана на тип события и
  **существовала на момент события**. Хук, созданный позже, не виноват, что не
  получил старое событие — и не может заблокировать вердикт `delivered`, даже
  если событие висит в очереди из-за него.
- Фронт: `pages/admin/AdminReconciliationPage.tsx` — фильтр по датам, полоса
  сводки, фильтр по статусу доставки, текст ошибки под бронью. В навигации
  админки — «Сверка».

#### Инварианты, проверенные и тестами, и живьём
1. **Подтверждённая бронь с живым хуком → `delivered`** — сверка считает ровно
   то, что записал воркер.
2. **Хука нет / выключен → `no_listener`**, и это не влияет на счётчик ошибок.
3. **Dead-letter → `failed`** с текстом ошибки в карточке брони.
4. **Событие в полёте → `queued`**; опубликованное без доставок →
   `undelivered`.
5. **Отмена важнее подтверждения** — бронь судят по последнему событию
   (`booking.cancelled`), а не по подтверждению до него.
6. **Диапазон и origin**: фильтрует по дате создания брони; бронь гостя
   напрямую (`origin='web'`) в отчёт не попадает.
7. **Живьём**: создал бронь без хука → `no_listener`; поднял локальный
   приёмник, подписал, создал бронь → воркер доставил, сверка показала
   `delivered` и `delivered_ok/expected` по подпискам.

## Гейты / тесты — всё зелёное

- `uv run pytest tests/ -q` — **162 passed**: 70 + 13 ical-import + 13 channel
  + 15 outbox + 15 channel-read + 10 ratelimit + 11 reconciliation + 7 retention
  + 8 backlog (rollback с транзакцией, эмит не ломает бизнес, claim/reclaim,
  HMAC, частичный успех, dead letter, ретрай, эмит из всех точек)
  (парсер: unfolding, datetime-форма, RRULE/COUNT, отказы на unbounded RRULE и
  без DTSTART; apply: блокировка, разблокировка только своего, добивание
  inventory, брони не трогаются; sync: мок HTTP, запись ошибок).
- `uv run ruff check app tests scripts` — PASS.
- `npx tsc -b --noEmit` + `npm run build` — OK (dist 401 КБ JS).
- Гейт-скрипты `check_no_emoji.py` / `lint_hardcodes.py` /
  `validate_contrast.py`, упоминавшиеся ранее, **в репо отсутствуют** — если они
  нужны как гейты, их надо восстановить (или убрать из чек-листа).

### Проверки (живые)
- Создал фид партнёром → `GET .ics` отдал валидный VCALENDAR; hold →
  STATUS:TENTATIVE с правильными DTSTART/DTEND; закрытый диапазон → одно
  CONFIRMED-событие; `wrongtoken.ics` → 404.
- **Кольцо export→import**: закрыл 4 дня на UT1 (manual) → фид отдает одно
  VEVENT → подписал UT2 → `sync` → `blocked:4`, `closed_source='import'`;
  `create_hold` на закрытую дату → 409, на открытую → 201; открыл UT1 обратно →
  `sync` → `cleared:4`.

## Архитектурные решения, которые важно знать

- **Double booking невозможен по архитектуре**: hold внутри SERIALIZABLE +
  `FOR UPDATE` с упорядоченной блокировкой `(unit_type_id, date)`; инвариант
  `hold+sold <= total_units` в транзакции. Любой канал, который будет писать
  брони (write-API), обязан идти через этот же путь.
- **Outbox появился в Phase 3** и закрыл «мы → внешний»: события пишутся в
  ту же транзакцию, воркер доставляет по webhook-подпискам. Export остаётся
  pull (iCal), import и write-API — push в нас.
- **Комиссия снапшотится** при подтверждении; отчёты не пересчитывают.
- **Пароль — SHA-256 заглока**, заменить на argon2 перед боем (то же касается
  API-ключей каналов).

## Что дальше по плану

0. **РЕДИЗАЙН (отложенный, но запланированный)** — текущий визуал не
  устраивает, будет отдельный срез. Менять: бренд, палитру, эстетику
  компонентов. Что остаётся как каркас и **не** переписывается: токен-система
  Меняем содержимое палитры через `scripts/gen_palette.py` (BRAND_HUE
  и шаги рампы) + `emit_tokens.py`, не правя руками `theme.css`.
1. **Шардинг outbox** — один воркер на всю очередь; при росте — по property.
2. **Закрыть долги безопасности** — argon2 для паролей и API-ключей,
   sealed column для секретов вебхуков (см. «Известные долги»). Очередь теперь
   ограничена (shedding + приоритет), а вот секреты всё ещё plaintext.

### Известные долги
- Регистрации на UI нет (бэк `POST /v1/auth/register` есть); стафф заводится в
  БД намеренно.
- Гость-флоу захардкожен demo-гость в `BookingPanel.tsx`.
- Skip-link, UI тёмной темы (см. AUDIT-design-a11y.md).
- В seed_demo нет подтверждённых броней — отчёт комиссии в демо показывает нули
  (empty state обрабатывает); iCal-фид в демо тоже пустой, пока не создать бронь.
- `window.location.replace` после логина вместо инвалидации кеша TanStack.
- **Тесты стирают дев-базу**: `committed_conn` гоняет `DELETE` по всем таблицам
  в той же `hotel_mp`, где живёт demo-данные. После `pytest` дев-сервер
  отвечает 404 на всё, что завязано на сид — пересей `seed_demo.py`. Для CI
  нужна отдельная БД.
- Poller импорта ходит во внешние календари из коробки: на локали без интернета
  fetch падает по таймауту и пишет `last_status='error'` — это норма.
- **API-ключи каналов — SHA-256**, как и пароли. Перейти на argon2 вместе с
  паролями перед боем. Утечку ключа сейчас не отследить — нет логирования
  доступа по ключу (только `last_used_at`).
- **Секрет webhook-подписки хранится plaintext** — нужен sealed column / vault
  до прода. Сейчас секрет знает только партнёр и наша БД.
- Write-API не валидирует диапазон дат канала дальше базовой доступности —
  для боевого подключения канала нужна сверка тарифов.

## Запуск

```
cd /Users/guuu/Desktop/hotel-marketplace
uv run python -m app.db.migrate            # 16 миграций
uv run python scripts/seed_demo.py         # partner + admin + 2 отеля
uv run uvicorn app.main:app --port 8002    # бэк + prod-фронт из web/dist
cd web && npm run dev                      # дев-фронт :5173, прокси /v1 → :8002
uv run pytest tests/ -q                    # 162 теста
cd web && npx tsc -b --noEmit
```

Демо-входы: партнёр `demo@example.com / demo-password`, админ
`admin@example.com / admin-password`. БД: hotel_mp (hotel_user / hotel_pass).

### 9. Retention для webhook_delivery (Phase 3, срез 5)

Лог доставки рос без ограничений (каждое событие × каждая подписка), а на него
опирается reconciliation — дропать старое нельзя, его надо старить сознательно.

- `migrations/0015__webhook_delivery_retention.sql` — таблица теперь
  RANGE-партицирована по `delivered_at` помесячно (`webhook_delivery_YYYYMM`)
  плюс DEFAULT-партиция; миграция переносит существующие строки.
- `app/modules/outbox/retention.py` — джоба `retention_loop` в lifespan:
  создаёт партиции на N месяцев вперёд, удаляет `success` старше
  `webhook_delivery_success_days` (30) и `failed` старше
  `webhook_delivery_failed_days` (365), дропает пустые партиции старше окна.
- `record_delivery` переписана с `ON CONFLICT` на update-then-insert:
  уникальность `(event_id, subscription_id)` теперь per-partition (глобальный
  индекс без ключа партицирования невозможен), FK ушли — партицированная
  таблица не может ссылаться наружу.
- Сверка переживает прореженный ledger: `delivered` деградирует до `partial`
  (часть доказательств стёрта) или `undelivered` (все) — те же статусы, что и у
  реально недошедшей доставки.

### 10. Лимит на backlog очереди (Phase 3, срез 6)

Очередь росла без ограничений, а воркер разгребает её на `webhook_rate_per_sec`
на подписку. Массовая операция (загрузка тарифов, iCal-импорт сезона) клала
тысячи событий, и бронь — единственное событие, которое стоит денег, — ждала в
конце очереди.

- `migrations/0016__outbox_backlog_limit.sql` — `priority` в `outbox_event`
  (`1` для booking, `9` для массовых), индекс под упорядоченный claim,
  `outbox_shed_counter` — счётчик сброшенных событий, одна строка на тип.
- `app/modules/outbox/backlog.py` — глубина очереди (`pending`+`delivering`),
  решение `admit()` (бронь всегда входит, масса — пока есть место), запись в
  счётчик.
- `service.emit()` — сверх `outbox_max_pending` (2000) массовое событие
  сбрасывается, считается и логируется, а не встаёт в очередь. Сброс безопасен:
  канал вытягивает тарифы и доступность через read-API и iCal.
- `claim_due` — `ORDER BY priority, next_attempt_at, happened_at`; RETURNING
  переупорядочивается в Python, потому что UPDATE пересканирует таблицу.
- `queue_metrics` отдаёт пороги (`depth_limit`, `lag_alert_sec`) и `shed_total`,
  чтобы UI рисовал линии, которые реально настроены.
- Фронт: «В очереди N / лимит», «Сброшено лимитом» + два алерта — достижение
  лимита (идёт shedding) и отставание очереди.

**Живые проверки**: 2600 изменений цен при задушенной подписке → глубина встала
на 2000, 600 событий сброшены и посчитаны; бронь через channel-API при
переполненной очереди доставлена (`published`, 200), пока ~1860 rate-событий
ещё ждали.

**Гейты**: 162 теста, ruff, tsc/build.
