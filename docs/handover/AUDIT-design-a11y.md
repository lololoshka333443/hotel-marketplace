# Дизайн-ревью + a11y-аудит (WCAG 2.2 AA)

Аудит `web/src/**` по `workflows/design-review.md` (6 измерений, Nielsen) и
`skills/a11y-audit` (WCAG 2.2 + ARIA patterns). Контраст измерён скриптами из
ux-ui-agent-skills (`scripts/contrast.py`), не на глаз. Браузер к сессии не
подключён, поэтому раскладка проверялась по коду + сборке; ручные протоколы
(клавиатура, скринридер, 320px) отмечены как доверенные.

## Скор (6 измерений)

| # | Измерение | Вес | Оценка | Комментарий |
|---|-----------|-----|--------|-------------|
| 1 | Visual Hierarchy | 20% | 8 | Тип-масштаб Major Third, один фокусный CTA на экран, hero со scrim |
| 2 | Consistency | 20% | 8 | Токены везде; было 2 расхождения (CTA-лейблы, одноразовые селекты) — закрыты |
| 3 | Accessibility | 20% | 7 | Было 5: 4 контрастных провала + отсутствие title/live-регионов — закрыты; осталось skip-link и UI тёмной темы |
| 4 | Usability | 20% | 8 | Было 6: no-op селект, бронь только первого номера, скрытая ошибка дат — закрыты |
| 5 | Responsiveness | 10% | 8 | Mobile-first, грибы коллапсят; шахматка — data-table, 2D-скролл легален (1.4.10) |
| 6 | Performance | 10% | 8 | WebP + lazy, eager hero с fetchPriority, бандл 364 КБ (gzip 112) |

**Итог: 7.8 / 10** — good, мелкий polish до ship-стандарта (9+).

## Находки

| # | Severity | Категория | Локация | Что не так | Исправление | WCAG / Nielsen |
|---|----------|-----------|---------|------------|-------------|----------------|
| 1 | Critical | A11y | ChessBoard, ячейка closed | Иконка замка 1.93:1 на action-secondary | text-tertiary → text-secondary (3.98:1 l / 4.38:1 d) | 1.4.11 |
| 2 | Critical | A11y | Input + все селекты | Бордер 1.39:1 — контур контрола не виден | border-default → border-strong (3.29:1 l / 4.19:1 d) | 1.4.11 |
| 3 | Critical | A11y | Мелкий шрифт везде | tertiary на белом 2.30:1 — fine print не читается | → text-secondary (4.75:1 l) | 1.4.3 |
| 4 | Critical | A11y | HomePage hero | Белый текст на произвольной фотографии — контраст не гарантирован | scrim-панель из токена `bg-scrim` | 1.4.3 |
| 5 | Critical | A11y | Все страницы | Один `<title>` на всё SPA | `hooks/useDocumentTitle.ts`, title на каждом экране | 2.4.2 |
| 6 | Major | A11y | BookingPanel | Ошибка `availability.get` не показывается — тык «Проверить даты» без результата | `role="alert"` + текст ошибки | 4.1.3, H9 |
| 7 | Major | A11y | HomePage / SearchPage / PropertyPage / ChessBoard | Loading и ошибки не анонсируются | loading → `role="status"`, error → `role="alert"` | 4.1.3 |
| 8 | Major | Usability | PartnerCalendarPage | Селект объекта no-op: опции рисуются, шахматка всегда по `first.id` | state + `ChessBoard propertyId` переключается | 3.2.2, H2 |
| 9 | Major | Usability | PropertyPage | Бронирование захардкожено на `unitTypes[0]` — остальные номера нельзя забронировать | Селектор «Номер» над BookingPanel | H2, H5 |
| 10 | Minor | Consistency | HomePage vs SearchPage | CTA карточек «Подробнее» vs «Посмотреть объект» | Унифицировано до «Подробнее» | 3.2.4, H4 |
| 11 | Minor | A11y | lint_hardcodes | 3 добольных значения (0.01ms ×2, min-h-[420px]) | Оформлены как `ds-allow-hardcode` с обоснованием | — |
| — | Enhancement | A11y | AppLayout | Нет skip-link к `<main>` | Добавить; формально 2.4.1 закрыт лендмарками (header/nav/main/footer), но skip-link — best practice | 2.4.1 |
| — | Enhancement | A11y | Нет UI тёмной темы | `[data-theme]` + prefers-color-scheme работают, переключателя нет | Добавить toggle в шапку | — |
| — | Enhancement | Tokens | Палитра | Токен `--t-text-tertiary` проходит AA не на всех фонах (2.30:1 на белом); системно лечится в `gen_palette.py`, а не точечно | Поднять tertiary до ≥4.5:1 на белом в скрипте палитры | 1.4.3 |
| — | Enhancement | Usability | Поиск | У инпута поиска нет видимого лейбла (aria-label есть) | Видимый лейбл или сохранить | 3.3.2 |

## Подтверждённые проходы (что уже было сделано хорошо)

- **1.1.1** — все `<img>` с осмысленным alt; lucide-иконки `aria-hidden="true"`.
- **1.3.1** — реальные `<table>`/`<th scope>`/`<caption>` в шахматке, `<dl>` в
  чекауте, оборачивающие `<label>` на формах.
- **1.4.1** — состояние ячеек шахматки = иконка + цвет + число; бейджи со
  текстом; ошибки с текстом, не только красным.
- **2.1.1 / 2.1.2** — нативные контролы; Modal: focus trap, Escape, возврат
  фокуса, `aria-modal` + `aria-labelledby`.
- **2.4.3 / 2.4.7** — фокус на первый focusable в модалке; глобальный
  `:focus-visible` ring 3.30:1 (l) / 5.44:1 (d).
- **2.5.8** — цели ≥32px (size-control-sm = 2rem); ячейки шахматки 36px.
- **3.3.1 / 3.3.8** — ошибки текстом через `role="alert"`; логин без CAPTCHA,
  поддержка менеджеров паролей.
- **3.1.1** — `<html lang="ru">`.
- **Reduced motion** — на уровне токена и global media query.
- **Dark mode** — две стратегии (data-theme выигрывает, иначе prefers-scheme),
  все контрастные пары измерены в обеих темах.

## Измерения (финал)

| Пара | Light | Dark | Норма |
|------|-------|------|-------|
| secondary on action-secondary (closed cell) | 3.98:1 | 4.38:1 | 3:1 UI |
| border-strong (input border) | 3.29:1 | 4.19:1 | 3:1 UI |
| secondary on page (fine print) | 4.75:1 | 7.79:1 | 4.5:1 text |
| focus ring on page | 3.30:1 | 5.44:1 | 3:1 UI |
| error/warning/info/success text on своих bg | 6.97–9.45:1 | 5.96–8.24:1 | 4.5:1 ✓ |
| hero: white on scrim (худший случай, чисто-белое фото) | 3.41:1 | 18.08:1 | large 3:1 ✓ |
| hero: white на scrim + градиент (реальный фон) | ≥ 7:1 | — | 4.5:1 ✓ |

## Не закрыто (осознанные долги)

- Регистрация партнёра (бэк есть, UI нет), demo-гость в BookingPanel —
  следующим срезом.
- Мьютации `hold/pay/create` показывают бэкендовский `detail` — это
  человекочитаемые сообщения, не стек-трейсы; fallback-строки прописаны.

## Закрыто позже

- **Skip-link** в `AppLayout`, **переключатель тёмной темы** в шапке
  (`hooks/useTheme.ts`, инлайн-скрипт в `index.html` до покраски) и
  **токен tertiary поднят до 4.50:1 на белом** — теперь он выводится в
  `gen_palette.text_grade()`, а не выбирается из рампы; регрессионные
  проверки — в `report()`. Видимый лейбл у инпута поиска добавлен.
