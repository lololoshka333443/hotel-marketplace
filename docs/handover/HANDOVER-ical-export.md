# Handover prompt: UX-тексты + логин + a11y + админка + iCal export + iCal import

Вставь этот текст в начало нового чата, чтобы передать контекст.

---

Проект: B2B2C маркетплейс бронирования жилья (Крым, Коктебель). Стек: Python 3.12
+ FastAPI + asyncpg + PostgreSQL 16 (бэк), React 18 + TypeScript + Vite 6 +
Tailwind 4 (фронт, single-app). Исходник правды — наша PostgreSQL; внешние
площадки — каналы (Phase 2). Бэк Phase 1 + админка + iCal export + iCal import
готовы (83 теста). Подробности — docs/ARCHITECTURE.md и README.

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
- `settings.app_base_url` — публичный origin для ссылок (дефолт
  `http://localhost:8000`, в проде выставить реальный домен).

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

## Гейты / тесты — всё зелёное

- `uv run pytest tests/ -q` — **83 passed**: 70 предыдущих + 13 ical-import
  (парсер: unfolding, datetime-форма, RRULE/COUNT, отказы на unbounded RRULE и
  без DTSTART; apply: блокировка, разблокировка только своего, добивание
  inventory, брони не трогаются; sync: мок HTTP, запись ошибок).
- `uv run ruff check app tests scripts` — PASS.
- `npx tsc -b --noEmit` + `npm run build` — OK (dist 384 КБ JS).
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
- **Outbox не нужен для Phase 2**: export — pull (мы отдаём), import и write-API —
  push в нас. Outbox появится в Phase 3, когда понадобится мы → внешний
  (webhooks, sync тарифов, reconciliation).
- **Комиссия снапшотится** при подтверждении; отчёты не пересчитывают.
- **Пароль — SHA-256 заглока**, заменить на argon2 перед боем.

## Что дальше по плану

0. **РЕДИЗАЙН (отложенный, но запланированный)** — текущий визуал не
  устраивает, будет отдельный срез. Менять: бренд, палитру, эстетику
  компонентов. Что остаётся как каркас и **не** переписывается: токен-система
  (`theme.css` + `@theme inline` bridge), WCAG-покрытие, a11y-архитектура.
  WCAG-покрытие, a11y-архитектура. Меняем содержимое палитры через
  `scripts/gen_palette.py` (BRAND_HUE и шаги рампы) + `emit_tokens.py`, не
  правя руками `theme.css`. Сначала write-API (фундамент), потом редизайн
  сверху готовой системы.
1. **Write-API адаптер канала** — внешний толкает брони через API-ключ через
   тот же `create_hold`. Единственный оставшийся канал Phase 2.
2. **Outbox + sync worker** — в начале Phase 3 (webhooks наружу).

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

## Запуск

```
cd /Users/guuu/Desktop/hotel-marketplace
uv run python -m app.db.migrate            # 12 миграций
uv run python scripts/seed_demo.py         # partner + admin + 2 отеля
uv run uvicorn app.main:app --port 8000    # бэк + prod-фронт из web/dist
cd web && npm run dev                      # дев-фронт :5173, прокси /v1 → :8000
uv run pytest tests/ -q                    # 83 теста
cd web && npx tsc -b --noEmit
```

Демо-входы: партнёр `demo@example.com / demo-password`, админ
`admin@example.com / admin-password`. БД: hotel_mp (hotel_user / hotel_pass).
