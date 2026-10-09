# Handover prompt: запуск проекта с GitHub

Вставь этот текст в начало нового чата, чтобы передать контекст.
Подробная история по срезам — в `docs/handover/HANDOVER.md` (разделы «Что
сделано в этом срезе»), `docs/handover/HANDOVER-ical-export.md`,
`docs/ARCHITECTURE.md`.

---

Проект: B2B2C маркетплейс бронирования жилья (Крым, Коктебель). Партнёры
заводят объекты в нашем кабинете, гости бронируют и платят у нас, комиссия с
подтверждённой брони. Instant book, 100% предоплата, отмена бесплатна за
сутки до заезда. PostgreSQL — источник правды, внешние площадки (Avito,
Суточно.ру, Яндекс, Airbnb) — каналы, не главный календарь. Double booking
невозможен по архитектуре.

**Репозиторий:** https://github.com/lololoshka333443/hotel-marketplace
(приватный, ветка `main`, дерево чистое).

## Шаг 0. Получи код

Если папки `/Users/guuu/Desktop/hotel-marketplace` на этой машине нет — склонируй:

```bash
git clone https://github.com/lololoshka333443/hotel-marketplace.git ~/Desktop/hotel-marketplace
cd ~/Desktop/hotel-marketplace
```

Если папка уже есть, просто подтяни свежее:

```bash
cd /Users/guuu/Desktop/hotel-marketplace
git pull --ff-only
```

Все коммитишь в `main` и пушаешь обратно (`git push`). Коммиты — conventional
commits на английском: `feat:`, `fix:`, `docs: handover — …` (историю и
конвенцию смотри в `git log --oneline`). Перед началом работы всегда
убедись, что `git status` чистый.

## Шаг 1. Окружение

Стек: Python 3.12 + FastAPI + asyncpg + PostgreSQL 16 (бэк, **без ORM, чистый
SQL**, ручные `.sql`-миграции), Redis, React 18 + TypeScript + Vite 6 +
Tailwind 4 (фронт, single-app — бэк раздаёт `web/dist`). Локально postgres@16
и redis запущены через Homebrew.

```bash
uv sync --extra bot                    # бэкенд + aiogram
cp .env.example .env                   # .env в git не лежит — создаётся из примера
```

После копирования `.env` **обязательно** сгенерируй секреты — в примере они
пустые/дефолтные, и без них приложение не поднимется:

```bash
python -c "from cryptography.fernet import Fernet; print('WEBHOOK_SEAL_KEY=' + Fernet.generate_key().decode())"
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
```

`DATABASE_URL` по умолчанию `postgresql://hotel_user:hotel_pass@localhost:5432/hotel_mp`.
Если базы и юзера ещё нет, создай их (psql от рута), затем:

```bash
uv run python -m app.db.migrate         # миграции
uv run python scripts/seed_demo.py      # демо-данные: партнёр и объекты в Коктебеле
uv run uvicorn app.main:app --port 8002 # API + собранный фронт на :8002
```

Фронт после правок пересобирается: `cd web && npm install && npm run build`.
Проверка типов: `cd web && npx tsc -b --noEmit`. Дев-порт 8002 (8000 занят
другим проектом), фронтовый дев-прокси следует за ним через `web/.env.local`.

## Шаг 2. Гейты (обязательны перед коммитом)

```bash
uv run pytest tests/ -q                 # ~280 тестов; suite сам поднимает hotel_mp_test
uv run ruff check app tests && uv run ruff format app tests
cd web && npx tsc -b --noEmit && npm run build
```

Тесты гоняются в отдельной базе `hotel_mp_test` (создаётся и дропается за
сессию, см. `tests/conftest.py`, `scripts/mk_test_db.py`), дев-базу `pytest`
не трогает. Все четыре гейта должны быть зелёными — это проектный стандарт.

## Шаг 3. Что читать

В порядке: `README.md` → `docs/ARCHITECTURE.md` (полный блюпринт: сервисы,
SQL-схема, алгоритмы, план по фазам) → `docs/HANDOVER.md` → `docs/handover/HANDOVER.md`
(хронология срезов) → `docs/LEGAL.md` (юр/налоги — паркинг для юриста).

API — всё под `/v1`: auth (register/login/me), partner (properties, unit-types,
inventory/generate, inventory/close, rate-plans, prices, calendar), public
(properties, availability), booking (hold с `Idempotency-Key`, GET, cancel,
pay, refund), admin (reports/commission, moderation, outbox), healthz/readyz.

Структура: `app/modules/{auth,property,inventory,booking,payment,rate,admin,notification}/`,
`app/{jobs/reaper.py, db/{pool,migrate}.py, config/}`,
`migrations/0001..0022*.sql`, `web/src/{pages/{guest,partner},components/ui,api/}`,
`tests/`.

## Шаг 4. Состояние проекта

- **Phase 1** — каталог, поиск, hold → оплата (stub) → confirm, кабинет
  партнёра (шахматка, цены, stop sell, список броней, удобства), уведомления.
- **Phase 2** — админка (модерация, отчёты по комиссии), iCal export/import,
  channel write-API.
- **Phase 3** — outbox + webhook-доставка, channel read-API, rate-limits,
  reconciliation, retention. **Закрыта.**
- **Харденинг** — argon2id для паролей и API-ключей, секрет webhook-подписки
  опечатан (`WEBHOOK_SEAL_KEY`), ротация ключа без даунтайма
  (`WEBHOOK_SEAL_KEY_PREVIOUS` + `scripts/rotate_seal_key.py`).
- **Редизайн «paper and ink»** — переведена вся аппка. **Больше не трогать**:
  палитра только через `scripts/gen_palette.py` + `scripts/emit_tokens.py`,
  `theme.css` руками не править. Тема одна, светлая — переключателя
  намеренно нет.

**Открытый долг:** i18n (английский) — **отложен на самый дальний край
шкафа**, это не сейчас и ничего не блокирует (~1400 строк в 25 файлах фронта,
i18next + react-i18next, 4–6 дней; детали в `docs/handover/HANDOVER.md`).
Явного срочного долга нет — естественное продолжение следующий сценарий из
`docs/ARCHITECTURE.md` в рамках темы «механика сайта» (гостевой путь, кабинет
партнёра, админка как пользовательские сценарии, а не инфраструктура).

## Шаг 5. Нюансы, которые надо помнить

- Часовой пояс Крыма — `Europe/Simferopol` (не Asia).
- Комиссия снапшотится при подтверждении; отчёты её не пересчитывают.
- `total_units` у unit-type нельзя менять через PATCH — это потолок
  инвентаря, под который блокируется бронирование.
- Seed: перезапуск привязывает все объекты к текущему партнёру; фото
  партнёров при re-seed не стираются.
- Оплата — заглушка `PAYMENT_MODE=stub`; реальный эквайринг = реализация того
  же интерфейса `PaymentProvider`.
- Юр/налоги — `docs/LEGAL.md`, в коде константы `app/config/legal.py`.
  Отвечаем только за технику.

**Не трогать:** инварианты брони (SERIALIZABLE + `FOR UPDATE`), outbox-механику
(включая шардирование и retention), iCal, опечатывание секретов, дизайн-систему.

## Шаг 6. В конце сессии

Обнови handover-документ: допиши раздел «Что сделано в этом срезе» в
`docs/handover/HANDOVER.md` (что сделал, какие файлы затронуты, какие живые
проверки провёл), обнови шапку-промт этим файлом, закоммить
(`docs: handover — …`) и запушь. Следующая модель должна стартовать с этого
документа без твоих объяснений.
