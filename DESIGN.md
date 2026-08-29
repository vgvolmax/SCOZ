---
version: alpha
name: "SCOZ"
description: "Локальный Windows-инструмент для evidence-first диагностики Ozon SKU: спокойный, точный аналитический control desk вместо BI-конструктора."
colors:
  app-bg: "#F6F8FB"
  surface: "#FFFFFF"
  surface-muted: "#F8FAFC"
  surface-hover: "#F1F5F9"
  border: "#E2E8F0"
  border-strong: "#CBD5E1"
  control-border: "#64748B"
  control-border-hover: "#475569"
  text: "#0F172A"
  text-secondary: "#475569"
  text-muted: "#64748B"
  text-disabled: "#94A3B8"
  primary: "#2563EB"
  primary-hover: "#1D4ED8"
  primary-pressed: "#1E40AF"
  primary-soft: "#EFF6FF"
  primary-border: "#BFDBFE"
  success: "#16A34A"
  success-text: "#166534"
  success-soft: "#F0FDF4"
  success-border: "#BBF7D0"
  warning: "#D97706"
  warning-text: "#92400E"
  warning-soft: "#FFFBEB"
  warning-border: "#FDE68A"
  danger: "#DC2626"
  danger-text: "#991B1B"
  danger-soft: "#FEF2F2"
  danger-border: "#FECACA"
  info: "#0284C7"
  info-text: "#075985"
  info-soft: "#F0F9FF"
  info-border: "#BAE6FD"
typography:
  sans:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
rounded:
  DEFAULT: "10px"
  sm: "6px"
  control: "8px"
  card: "10px"
  large: "12px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  base: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "40px"
  xxxl: "48px"
components:
  appShell: {}
  productContextHeader: {}
  evidenceRail: {}
  workspaceTabs: {}
  productCatalogTable: {}
  button: {}
  input: {}
  status: {}
  card: {}
---

# SCOZ Design System

## Overview

### Creative North Star

SCOZ должен ощущаться как **Analytical Control Desk**: профессиональный рабочий инструмент, где пользователь быстро выбирает объект анализа, видит состояние доказательной базы и движется от вывода к причинам и исходным фактам. Интерфейс не имитирует маркетинговый SaaS, универсальный BI-конструктор или CRM.

Визуальная структура должна помогать отвечать на три вопроса без чтения методологии:

1. какой SKU сейчас анализируется;
2. на каких данных стоит текущий вывод;
3. куда перейти, чтобы проверить причину или изменить контекст.

### Product context and register

- **Audience and primary job:** небольшая группа доверенных сотрудников компании; основной сценарий — диагностировать собственный Ozon SKU относительно выбранной группы прямых конкурентов и понять, где находится отставание.
- **Target market and evidence:** внутренний инструмент для работы с Ozon; бизнес-контекст определяется каноническими Product/UI/Architecture документами репозитория.
- **Locale and language policy:** v1 — русский пользовательский интерфейс. Английские имена доменных сущностей и внутренних модулей не должны просачиваться в пользовательскую лексику без необходимости.
- **Usage scene:** Windows desktop/laptop, частая аналитическая работа, целевая ширина 1440–1600 CSS px, рабочая нижняя граница 1280 CSS px, Windows scaling 125–150%.
- **Register:** product/admin analytical tool. Task clarity, плотность данных, воспроизводимость и состояния важнее брендовой экспрессии.
- **Memorable signature:** **Evidence Rail** — компактная горизонтальная полоса под контекстом активного SKU, показывающая готовность и свежесть ключевых доказательных слоёв без интегрального score.
- **Restraint:** таблицы, фильтры, формы, import/history и настройки остаются спокойными и знакомыми; выразительность не должна мешать сравнению чисел.
- **Anti-references:** card-wall dashboards, Bootstrap/admin templates, CRM-like catalogs, glassmorphism, gradients, decorative 3D charts, oversized KPI walls, mobile-style pill-heavy desktop UI.
- **Token ownership/runtime mapping:** канонический источник визуальных token values — `docs/superpowers/specs/scoz-visual-design-system.md`; runtime mapping — `frontend/assets/css/app.css`. Этот `DESIGN.md` фиксирует durable taste/context и утверждённые workspace-паттерны, но не создаёт второй независимый token source. Любое изменение системного token value должно обновлять visual design system, `DESIGN.md` и runtime CSS в одном changeset.

### Current runtime token drift

На момент review 2026-08-29 `frontend/assets/css/app.css` ещё не полностью отображает канонический token contract. Это **migration debt**, а не новый источник истины и не причина менять CSS в документационном PR:

- runtime использует legacy `--color-error*`, тогда как canonical contract использует `danger` / `danger-text` / `danger-soft` / `danger-border`;
- runtime `--color-success` и `--color-warning` сейчас содержат readable text shades, тогда как canonical contract разделяет accent (`success` / `warning`) и readable text (`success-text` / `warning-text`);
- runtime пока не объявляет часть утверждённых tokens, включая `--color-primary-pressed`, `--color-text-disabled`, `--color-info*` и `--radius-pill`;
- новые frontend PR не должны копировать legacy runtime names как новый канон; при следующем материальном рефакторинге shared app shell/tokens drift устраняется отдельной complete migration slice с обновлением CSS и regression checks.

До этой migration существующий CSS остаётся рабочим runtime, а точные целевые token values определяет `docs/superpowers/specs/scoz-visual-design-system.md`.

### Product hierarchy

Глобальная IA остаётся:

- **Товары**;
- **Данные**;
- **Настройки**.

После выбора own SKU раздел `Товары` становится **Product Workspace**. Внутренние аналитические области не превращаются в глобальные sidebar sections:

- **Диагностика**;
- **Поиск**;
- **Разгон**;
- **Конкуренты**.

Runtime не должен показывать пустую/неработающую вкладку только потому, что она существует в target IA. Вкладка появляется, когда соответствующая feature vertical реально реализована; до этого пользователь не получает dead navigation.

## Colors

Палитра сохраняет уже утверждённый холодный нейтральный B2B-регистр:

- `app-bg` — фон приложения;
- `surface` — основные рабочие surfaces;
- `surface-muted` — вспомогательные области, technical detail и спокойные secondary states;
- `border` / `border-strong` — структура и разделение, а не декоративная рамка всего подряд;
- `primary` — активный контекст и главное действие;
- success/warning/danger/info — только semantic state, никогда не декоративная окраска больших частей страницы.

Evidence Rail использует прежде всего нейтральную типографику и компактные markers. Semantic color всегда сопровождается текстом состояния (`готово`, `недостаточно данных`, `устарело`, `ошибка`) и никогда не является единственным носителем смысла.

Диагностические delta и benchmark position не должны превращать экран в красно-зелёную тепловую стену. Один смысловой вывод может получить semantic accent; остальные значения остаются нейтральными.

## Typography

Основной offline-safe stack — `Segoe UI Variable Text` / `Segoe UI` / system UI. Remote web fonts запрещены.

Нормативная scale остаётся из канонического visual design system:

- Page title: 28/34, 700;
- Section title: 18/26, 600;
- Card title: 15/22, 600;
- Body: 14/20, 400;
- Table: 13/18, 400;
- Caption: 12/16, 400;
- KPI value: 24/30, 700;
- Compact KPI: 18/24, 600.

Числа, SKU, даты и delta используют `font-variant-numeric: tabular-nums` там, где поддерживается. Моноширинный шрифт не является частью фирменной идентичности и используется только для настоящего technical raw detail (например, hash или source filename), если это улучшает разборчивость.

Пользовательская лексика единообразна:

- `Benchmark` в UI → **Группа сравнения**;
- `Core Benchmark` / `Benchmark details` → **Сравнение с группой**;
- `Result` → **Результат**;
- `Traffic` → **Трафик**;
- `Conversion` → **Конверсия**;
- `Offer` → **Предложение**;
- `Advertising` → **Реклама**.

Внутренние Python/domain names не диктуют пользовательский copy.

## Layout

### App shell

- global sidebar: ориентир `224px`;
- content padding: `24–32px`;
- section gaps: `24–32px`;
- main analytical workspace fluid, без искусственного `max-width: 1000px`;
- при >=1280 CSS px основной analytical screen не требует page-level horizontal scroll;
- raw/detail tables могут скроллиться внутри собственного контейнера.

### Products entry states

`Товары` имеет два режима, а не одну бесконечную ленту:

1. **Catalog First** — когда нет активного own SKU: `Мои товары` + поиск/управление каталогом.
2. **Workspace First** — когда пользователь открыл own SKU: Product Context Header + Evidence Rail + workspace tabs.

Полный каталог — вспомогательная административная поверхность. Он не должен вытеснять основной аналитический контекст после выбора SKU.

### Product Context Header

Компактный header содержит:

- product title;
- Ozon SKU / article, если доступен;
- небольшое фото только когда оно приходит из утверждённого источника; отсутствие фото не блокирует header;
- active business period;
- freshness;
- control `Сменить товар`;
- краткий benchmark/data context без стены KPI.

Header — не hero-banner.

### Evidence Rail

Evidence Rail располагается непосредственно под Product Context Header и суммирует доказательную готовность областей, например:

- **Товарные данные** — `16.08 · свежие`;
- **Поиск** — `данные есть` / конкретное ограничение;
- **Группа сравнения** — `8 товаров` / `не настроена`;
- **Разгон** — `мало истории` / иной честный readiness.

Это не score и не progress bar. Не выводить `Готовность 78%` или аналогичную псевдоточность.

При узкой desktop ширине Evidence Rail может переноситься на две строки; он не создаёт горизонтальную прокрутку всей страницы.

### Product catalog

Полный Ozon catalog — компактная semantic table, а не stack из больших cards. Основная задача — найти конкретный SKU и изменить его membership в `Мои товары`.

Обязательные элементы:

- search по title или Ozon ID;
- bounded server pagination;
- total/range;
- ясная action column;
- стабильная высота table surface во время paging/filter loading;
- сохранение контекста при возврате из SKU workspace.

## Elevation & Depth

Иерархия строится через surfaces, whitespace, border и typography.

- default cards: без заметной shadow;
- `--shadow-subtle` допустим как почти незаметное отделение крупной static surface;
- `--shadow-popover` только для действительно floating UI: dropdown, SKU switcher popover, dialog/popover;
- Evidence Rail и workspace tabs не «парят» и не получают декоративную тень;
- modal/drawer, если появятся, имеют очевидный layer, но не размывают фон ради эстетики.

## Shapes

- controls: `8px`;
- cards/analytical blocks: `10px`;
- large containers/dialogs: до `12px`;
- pill: только status/tag/chip;
- table rows и navigation не должны превращаться в набор отдельных округлых плиток.

Форма должна подчеркивать рабочий desktop-регистр. Избыточно круглые mobile-like controls запрещены.

## Components

### Foundational visual states

Для повторяющихся controls/surfaces обязательны применимые состояния:

- default;
- hover;
- focus-visible;
- pressed/active;
- selected/current;
- disabled с понятной причиной;
- busy/pending;
- success;
- warning;
- error;
- empty;
- no-results;
- stale/partial refresh.

Loading не должен менять footprint контейнера или двигать основные actions.

### Buttons and actions

Иерархия: emphasis × intent.

- solid primary — одно главное действие конкретного block/view;
- outline/secondary — обычные безопасные действия;
- ghost — tertiary navigation/detail;
- danger — только destructive/hard-to-reverse action и визуально отдельно от safe primary.

Action vocabulary стабильна. Кнопка `Сохранить группу` приводит к feedback `Группа сохранена`, а не к `Benchmark updated`.

### Navigation and data display

#### Sidebar

Только `Товары / Данные / Настройки`. Labels всегда видимы. Collapsible sidebar v1 не нужен.

#### Workspace tabs

`Диагностика / Поиск / Разгон / Конкуренты` — sub-navigation внутри активного SKU. Active state использует primary accent и устойчивый indicator; tab не выглядит как primary CTA.

#### Product switcher

`Сменить товар` открывает searchable chooser только собственных товаров. Оттуда доступно вторичное действие `Управление товарами`, ведущее к полному каталогу.

#### Product catalog table

Native semantic table для read/locate workflow. Sticky header допустим, если таблица имеет собственный scroll container и это не ломает zoom/accessibility.

Primary row action:

- не-owned → `Добавить в мои товары`;
- owned → compact status `Мой товар`, а removal — secondary/overflow action `Убрать из моих товаров`.

Checkbox `Свой товар` не является основным пользовательским паттерном управления ownership.

#### Core analytical comparison

PR7 Core Benchmark не является отдельным глобальным экраном. В пользовательской структуре это `Сравнение с группой` — evidence/drill-down внутри Product Workspace, прежде всего для `Диагностики` и при необходимости `Конкурентов`.

### Forms and overlays

Search fields имеют explicit clear button при непустом значении. Secret/token fields masked by default и при следующем затрагивании Settings получают accessible show/hide action.

Использовать native HTML controls там, где OS-owned popup/behavior приемлем. Searchable SKU switcher требует app-owned combobox/popover behavior, потому что product должен контролировать search, loading, empty и keyboard states.

Browser `alert()`, `confirm()`, `prompt()` запрещены для product UI.

### Iconography

Один bundled SVG family/set. Emoji не являются системными иконками. Icon-only actions всегда имеют accessible name; критические действия не зависят только от иконки.

### Motion

Motion — только state communication:

- hover/focus/selection transition: короткая и спокойная;
- opening popover/dialog: минимальная;
- async completion: без декоративного celebration;
- `prefers-reduced-motion` отключает необязательные transitions/animations.

Не использовать staggered page reveals или ambient animation в рабочем аналитическом интерфейсе.

### Content and data visualization

North Star presentation:

> **Ответ → причина → подтверждающие показатели → исходные данные.**

Диагностический screen не начинается с 13 равнозначных metric cards. Он сначала показывает один главный вывод и максимум 2–3 существенных фактора, затем раскрывает benchmark/evidence.

Числа форматируются по русскому интерфейсу: `31 200`, `52,6 ₽`, `11,4%`, `+12%`, `−3,1 п.п.`. Не показывать больше precision, чем поддерживает источник/model.

Fact, calculated metric и estimate должны быть различимы copy/context; цвет не заменяет provenance.

## Do's and Don'ts

- **Do:** всегда оставлять активный SKU и readiness его доказательной базы визуально очевидными.
- **Do:** использовать compact table/list для больших наборов и cards только для смысловых analytical blocks.
- **Do:** сохранять одну и ту же пользовательскую лексику между action, feedback и соседними экранами.
- **Do:** проектировать 1280–1600 CSS px и проверять Windows scaling 125–150% и zoom 200%.
- **Don't:** превращать `Товары` в длинную ленту одинаковых карточек из всего Ozon catalog.
- **Don't:** выносить `Benchmark`, `Рекламу`, `Поиск`, `Кластеры` в global sidebar.
- **Don't:** показывать dead tabs, synthetic readiness scores или аналитические выводы без source readiness.
- **Don't:** делать generic SaaS card wall, декоративные gradients или heavy shadow hierarchy.