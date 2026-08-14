# SCOZ — Visual Design System

**Дата:** 2026-08-14  
**Статус:** канонический visual design contract  
**Репозиторий:** `vgvolmax/SCOZ`

## 1. Назначение

Этот документ определяет, **как должен выглядеть SCOZ**.

Он не определяет новые функции, метрики, расчёты, navigation items или business behavior. Product behavior задают Product Spec, Architecture, UI/UX Design, Preflight Decisions и актуальный PR Development Plan.

Если визуальное решение требует придумать новую метрику, экран, score, кнопку, прогноз или раздел, которого нет в продуктовых документах, **его не добавлять**.

Цель visual system:

> сделать SCOZ современным, спокойным, точным и профессиональным desktop-first аналитическим продуктом, а не типичным admin-template или BI-конструктором.

Ключевое ощущение интерфейса:

> **современный B2B analytics product: много воздуха, высокая читаемость, спокойная плотность данных, тонкие границы, минимум декоративного шума.**

---

## 2. Визуальные принципы

### 2.1. Иерархия важнее количества элементов

Основной порядок:

> **ответ → причина → подтверждающие показатели → детали / исходные данные.**

Интерфейс не должен начинаться с сетки из 10–15 одинаковых KPI-карточек.

### 2.2. Data-dense, но не тесный

SCOZ — аналитический инструмент, поэтому таблицы и метрики могут быть плотными, но между смысловыми блоками всегда должен оставаться визуальный воздух.

### 2.3. Surface-first

Основной способ разделять блоки:

- белая surface;
- тонкая нейтральная border;
- отступы;
- typography hierarchy.

Тени используются редко и слабо. Карточка не должна выглядеть как «парящая плитка» без необходимости.

### 2.4. Цвет — смысл, а не украшение

Синий — primary interaction/accent.  
Зелёный, amber и красный используются только для semantic states.

Не раскрашивать весь экран статусными цветами.

### 2.5. Не выглядеть как Bootstrap/Admin template

Запрещён визуальный стиль:

- dashboard wall из одинаковых карточек;
- тяжёлые box-shadow;
- толстые borders;
- огромные marketing headings;
- перегруженная icon navigation;
- декоративные gradients;
- glassmorphism;
- 3D charts;
- цветные backgrounds на каждом блоке;
- чрезмерно скруглённые «мобильные» элементы на desktop.

---

## 3. Design tokens

Все значения должны быть централизованы как design tokens / CSS custom properties. One-off цвета, радиусы и spacing в отдельных компонентах без причины не допускаются.

### 3.1. Цвета

#### Base

```text
--color-app-bg:          #F6F8FB
--color-surface:         #FFFFFF
--color-surface-muted:   #F8FAFC
--color-surface-hover:   #F1F5F9
--color-border:          #E2E8F0
--color-border-strong:   #CBD5E1

--color-text:            #0F172A
--color-text-secondary:  #475569
--color-text-muted:      #64748B
--color-text-disabled:   #94A3B8
```

#### Primary

```text
--color-primary:         #2563EB
--color-primary-hover:   #1D4ED8
--color-primary-pressed: #1E40AF
--color-primary-soft:    #EFF6FF
--color-primary-border:  #BFDBFE
```

#### Semantic

```text
--color-success:         #16A34A
--color-success-soft:    #F0FDF4
--color-success-border:  #BBF7D0

--color-warning:         #D97706
--color-warning-soft:    #FFFBEB
--color-warning-border:  #FDE68A

--color-danger:          #DC2626
--color-danger-soft:     #FEF2F2
--color-danger-border:   #FECACA

--color-info:            #0284C7
--color-info-soft:       #F0F9FF
--color-info-border:     #BAE6FD
```

Semantic background должен быть очень светлым. Основной текст внутри banner/card остаётся тёмным; яркий цвет используется в icon, status label, delta или border accent.

### 3.2. Chart palette

Основной ряд:

```text
--chart-blue:    #2563EB
--chart-cyan:    #0EA5E9
--chart-teal:    #14B8A6
--chart-violet:  #8B5CF6
--chart-amber:   #F59E0B
--chart-red:     #EF4444
```

Не использовать все цвета одновременно. Для большинства SCOZ-графиков достаточно 1 primary series + 1 benchmark series + neutral observations.

### 3.3. Spacing scale

Базовая система:

```text
4 / 8 / 12 / 16 / 24 / 32 / 40 / 48 px
```

Правила:

- внутри небольшого control: 8–12 px;
- между связанными элементами: 8–12 px;
- padding обычной card: 16–20 px;
- padding крупного analytical block: 20–24 px;
- между самостоятельными блоками: 20–24 px;
- section gap: 24–32 px;
- page padding desktop: 24–32 px.

Не использовать случайные значения вроде 13, 19, 27 px без layout-причины.

### 3.4. Радиусы

```text
--radius-sm:     6px
--radius-control:8px
--radius-card:   10px
--radius-large:  12px
--radius-pill:   999px
```

Cards по умолчанию 10 px.  
Buttons/inputs — 8 px.  
Pill используется только для chip/status/tag.

### 3.5. Тени

Default cards не требуют заметной тени.

```text
--shadow-subtle: 0 1px 2px rgba(15, 23, 42, 0.04)
--shadow-popover: 0 8px 24px rgba(15, 23, 42, 0.10)
```

`shadow-popover` — только dropdown/modal/popover и аналогичные floating surfaces.

---

## 4. Типографика

Не подключать remote web fonts. SCOZ должен нормально выглядеть offline.

Основной stack:

```css
font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
```

### Scale

```text
Page title:       28px / 34px / 700
Section title:    18px / 26px / 600
Card title:       15px / 22px / 600
Body:             14px / 20px / 400
Body strong:      14px / 20px / 600
Table:            13px / 18px / 400
Table strong:     13px / 18px / 600
Caption:          12px / 16px / 400
KPI value:        24px / 30px / 700
Compact KPI:      18px / 24px / 600
```

Правила:

- не использовать огромные H1 40–56 px;
- numeric values используют tabular numbers, если font/браузер поддерживает `font-variant-numeric: tabular-nums`;
- uppercase не использовать для длинных labels;
- muted text не должен становиться слишком светлым и терять читаемость;
- line-height важнее декоративной компактности.

---

## 5. App shell

### 5.1. Desktop target

SCOZ оптимизируется для обычного Windows desktop/laptop.

Целевой CSS viewport:

- оптимально: 1440–1600 px width;
- основной интерфейс должен оставаться usable от 1280 px width;
- при Windows scaling 125–150% не должно быть overlap/clipping;
- main analytical screens при >=1280 CSS px не требуют page-level horizontal scroll;
- raw/detail tables могут иметь свой horizontal scroll.

### 5.2. Sidebar

Глобальная sidebar содержит только утверждённую IA:

- **Товары**;
- **Данные**;
- **Настройки**.

Не добавлять `Dashboard`, `Analytics`, `Reports`, `Users`, `Support`, `Regions`, `Categories` и другие пункты только ради привычного SaaS-вида.

Recommended width: `224px`.

Sidebar:

- светлая / white surface;
- right border вместо тяжёлой shadow;
- active item — primary-soft background + primary text/icon;
- icons вторичны и одинакового визуального веса;
- labels всегда видимы в v1; collapsible sidebar не требуется без отдельной необходимости.

### 5.3. Product Workspace

Внутри выбранного SKU основная navigation:

- **Диагностика**;
- **Поиск**;
- **Разгон**;
- **Конкуренты**.

Это tabs/sub-navigation workspace, а не новые глобальные sidebar sections.

### 5.4. Page content

Main workspace — fluid, без искусственно узкого marketing max-width.

Recommended:

```text
content padding: 24–32 px
main column gap: 20–24 px
```

Визуально страница строится крупными горизонтальными смысловыми уровнями, а не «мозаикой» из случайных карточек.

---

## 6. Product Context Header

На аналитических экранах Product Workspace используется единый compact header.

Он показывает:

- небольшое фото own product;
- title;
- SKU / article;
- active business period;
- freshness;
- benchmark status/composition;
- data readiness только в конкретных понятных статусах.

Не показывать в header много KPI.

Recommended layout:

- product image 56–72 px;
- product identity слева;
- context/status справа;
- header height определяется content, но не превращается в hero-banner.

Примеры корректных readiness labels:

- `Benchmark — 8 конкурентов`;
- `История позиций — 21 день`;
- `Данные Ozon — свежие`;
- `Разгон — данных недостаточно`.

Не использовать интегральные проценты вроде `Готовность 78%`, если такой score не определён продуктовой моделью.

---

## 7. Cards и analytical blocks

### Default card

```text
background: surface
border: 1px solid border
radius: 10px
padding: 16–24px
shadow: none или subtle
```

Карточка должна иметь смысловую роль, а не быть обязательной оболочкой любого текста.

### KPI cards

KPI-card используется только для действительно первичного числа.

Не более 3–5 primary KPI cards на одном смысловом уровне.

Каждая KPI card может содержать:

- label;
- own value;
- benchmark/context;
- delta;
- status;
- небольшой sparkline только если trend реально важен.

Не добавлять sparkline как декоративный элемент без временного ряда.

### Diagnosis banner

Один главный diagnosis banner допускает semantic soft background.

Структура:

- icon/status;
- короткий headline;
- 1–2 строки объяснения;
- confidence/limitation при необходимости;
- одна secondary action только если она реально ведёт к существующему workflow.

---

## 8. Buttons и controls

### Sizes

```text
Default control height: 36px
Primary prominent action: 40px допустимо
Compact table action: 32px
Icon button: 32–36px
```

### Primary button

Используется для одного главного действия в конкретном block/view.

Примеры:

- `Загрузить отчёт`;
- `Сохранить ревизию`;
- `Проверить подключение` только если это главное действие текущего блока.

Не делать несколько одинаково ярких primary buttons рядом.

### Secondary / ghost

Secondary — border + surface.  
Ghost — без border/background по умолчанию.

### Focus

Keyboard focus всегда видим.

Recommended focus treatment:

```text
2px primary focus ring + 2px offset
```

Hover не является единственным способом показать доступность действия.

### Disabled

Disabled state должен отличаться не только opacity: текст, cursor и background/border также нейтрализуются.

---

## 9. Inputs, filters, select

Input/select/filter визуально компактные, высота около 36 px.

- labels используются там, где поле неочевидно;
- placeholder не заменяет label для критичных fields;
- filter chips показывают выбранное состояние;
- active filter не должен выглядеть как primary CTA;
- search box не занимает половину экрана без необходимости.

Errors показываются рядом с соответствующим control человеческим текстом.

---

## 10. Status chips

Chip/status — компактный semantic indicator, не самостоятельная карточка.

Recommended statuses:

- success: green text + soft green background;
- warning: amber text + soft amber background;
- danger: red text + soft red background;
- neutral: slate text + muted background;
- info/current: blue text + primary-soft background.

Цвет всегда дублируется текстом или symbol/icon.

Не делать красный/зелёный единственным носителем смысла.

---

## 11. Tables

Таблицы — основной визуальный инструмент для многомерной аналитики SCOZ.

### Основной стиль

- white surface;
- тонкие горизонтальные separators;
- минимальное количество vertical borders;
- header с muted background или plain surface;
- header text 12–13 px / 600;
- numeric columns right-aligned;
- row hover очень мягкий;
- selected row — primary-soft background + optional 2px left accent;
- zebra striping не использовать по умолчанию.

### Row heights

- обычная analytics row: 44–48 px;
- competitor row с thumbnail: 60–72 px;
- compact detail row: 36–40 px.

### Sorting/filtering

Sort state должен быть видимым, но не перегружать header icons.

### Missing data

Missing/unknown показывается как `—`, `Нет данных`, `Не наблюдалось` или другой точный domain state.

Никогда не заменять missing значением `0` только ради визуальной простоты.

---

## 12. Charts

График появляется только если он быстрее отвечает на вопрос, чем таблица.

### Общий стиль

- white/surface background;
- no chart frame внутри card, если card уже имеет border;
- gridlines: border/light neutral;
- axis text: text-muted;
- основной line width 2px;
- benchmark line может быть dashed;
- observations — neutral/light points;
- our/current point — primary или semantic highlight;
- confidence band — 8–12% opacity;
- tooltip — compact popover, без огромной таблицы.

### Запрещено

- 3D;
- decorative gradients;
- pie/donut для сложных сравнений;
- gauge ради «красивого процента»;
- больше 4–5 series на одном chart без сильной необходимости;
- красно-зелёное сравнение без labels.

### Sparklines

Использовать только при реальном time series.  
Без axes, grid и legend, если контекст однозначен.

---

## 13. Heatmap

Search Visibility heatmap является таблицей с semantic cell backgrounds, а не отдельной «картинкой».

Основные колонки:

`Кластер | Позиция | Релевантность | Популярность | Доставка | Цена`

Правила:

- text/value остаётся читаемым поверх background;
- status palette мягкая, без насыщенных красно-зелёных блоков;
- position может использовать отдельную numeric/status treatment;
- legend объясняет направление `лучше / хуже`;
- color не заменяет число;
- missing observation визуально отличается от плохого значения.

---

## 14. Screen composition

### 14.1. Диагностика

Вертикальный приоритет:

1. Product Context Header.
2. Один главный diagnosis/verdict banner.
3. 3–5 supporting metrics: результат, traffic, conversion, card/search-to-cart по доступности.
4. Compact offer + advertising-intensity context.
5. Benchmark evidence / competitor details.
6. Source/details по progressive disclosure.

Не показывать десятки KPI на первом уровне.

### 14.2. Поиск

Приоритет:

1. Product Context Header + active query context.
2. `Поисковые возможности` — prioritized table/list.
3. Пользователь выбирает query.
4. Ниже — cluster heatmap для выбранного query.
5. Короткое объяснение системной/локальной проблемы.
6. Position history/Share of Top — detail layer.

Query Opportunity не становится отдельным dashboard.

### 14.3. Разгон

Приоритет:

1. Readiness gate / verdict.
2. Короткое объяснение evidence и confidence.
3. `Позиция → Конверсия` chart, только если модель допустима.
4. Scenario table `Сейчас / TOP-20 / TOP-10 / TOP-3` с ranges.
5. Organic-support trend при достаточной истории.
6. Method/data limitations в detail layer.

Не использовать псевдоточные confidence percentages, бюджеты или «+N заказов», если конкретная аналитическая модель этого не возвращает.

### 14.4. Конкуренты

Desktop two-column pattern:

- left 65–70%: candidate list;
- right 30–35%: selected benchmark revision.

Candidate row:

- thumbnail;
- title;
- SKU;
- brand/price/context при наличии;
- include/exclude action.

Right panel:

- selected count;
- compact selected competitor rows;
- remove/reorder только если это реально нужно interaction model;
- одна primary action `Сохранить ревизию` / эквивалент.

Настройки API/ключей не смешиваются с competitor selection screen.

### 14.5. Данные

Data screen строится вокруг:

- imports/sync actions;
- history;
- period/source/freshness;
- import result states.

Не превращать его в technical admin console.

### 14.6. Настройки → Источники

Отдельные source cards/rows:

- source name;
- connection status;
- credentials controls;
- `Проверить подключение`;
- encrypted keystore actions.

Keystore UI должен выглядеть как обычный понятный settings block, а не security-product.

---

## 15. Loading, refresh и operation feedback

### Known layout

Использовать skeleton, если структура заранее известна.

Skeleton:

- повторяет реальную geometry;
- neutral gray;
- без агрессивной shimmer-анимации;
- не прыгает по высоте после загрузки.

### Short action

Button-local spinner / inline loading достаточно.

### Long action

Показывать human-readable stage:

- `Проверяем файл`;
- `Читаем данные`;
- `Нормализуем`;
- `Сохраняем`;
- `Обновляем аналитику`.

Процент — только если он честно вычисляется.

### Refresh with previous data

Старые данные остаются на месте, если безопасно, и получают compact label:

> `Обновляем… показаны предыдущие данные`.

Не заменять весь экран spinner-ом без необходимости.

---

## 16. Empty, stale, partial, insufficient и error states

### Empty

Показывает:

- что отсутствует;
- почему;
- одно следующее действие.

### Stale

Данные можно смотреть, но freshness явно помечена.

### Partial success

Показывать, что импорт/операция частично выполнена, сколько принято/пропущено и где детали.

### Insufficient data

Это полноценный analytical state, а не generic error.

Пример:

> **Пока недостаточно истории для оценки разгона.**
> Нужна история позиций и конверсии за сопоставимые периоды.

### Error

Primary message — человеческое.  
Technical details — только по раскрытию.

Raw stack trace в основном UI запрещён.

---

## 17. Modals, drawers, popovers

Использовать только когда они сохраняют контекст.

- confirmation для безопасных обратимых действий обычно не нужна;
- destructive/irreversible action требует confirmation;
- details предпочтительно раскрывать inline/drawer, если пользователь должен сравнивать с основным экраном;
- modal не должен использоваться как полноценная страница.

Popover/dropdown — единственные surfaces, где допустима заметная `shadow-popover`.

---

## 18. Numbers и formatting

Русские читаемые форматы:

```text
31 200
48 260 ₽
52,6 ₽
11,4%
+12%
−38%
+1,8 п.п.
1–2 дня
```

Правила:

- не показывать больше precision, чем даёт source/model;
- percentage и percentage points не смешивать;
- `—` не означает zero;
- ranges показывать en dash: `260–320 ₽`;
- большие числа сокращать только если это улучшает scanability и не теряет смысл (`31,2 тыс.` допустимо в KPI, полное значение — в detail/table).

---

## 19. Accessibility и interaction quality

Минимально обязательно:

- visible keyboard focus;
- logical tab order;
- semantic buttons/links/inputs;
- table headers связаны с данными;
- icon-only buttons имеют accessible label/tooltip;
- hover не является единственным способом раскрыть critical information;
- status color дублируется текстом/icon;
- contrast основных текстов и controls достаточен для долгой desktop-работы.

Не создавать tiny controls <32 px для основных действий.

---

## 20. Motion

Motion минимален.

Допустимо:

- hover/focus transitions 120–180 ms;
- dropdown/drawer 160–220 ms;
- skeleton/loading indicator.

Не использовать:

- spring/bounce animation;
- animated gradients;
- decorative chart entrance animation, мешающую сравнению;
- large page transitions.

Пользователь должен ощущать интерфейс быстрым, а не «анимированным».

---

## 21. Responsive behavior

SCOZ — desktop-first, не mobile-first.

При уменьшении ширины:

1. уменьшается whitespace в допустимых пределах;
2. вторичные context blocks могут переноситься на следующую строку;
3. detail tables получают внутренний horizontal scroll;
4. primary decision blocks остаются полностью видимыми;
5. sidebar не должна автоматически превращаться в mobile hamburger без отдельного v1 requirement.

Нельзя скрывать критичные метрики только ради responsive layout.

---

## 22. Visual anti-patterns для code review

PR требует корректировки, если UI:

- похож на generic Bootstrap/AdminLTE dashboard;
- вводит новые navigation items ради заполнения sidebar;
- показывает 8–15 одинаковых KPI cards одновременно;
- использует большие saturated status backgrounds;
- использует shadow вместо структуры/spacing;
- делает почти каждый block карточкой внутри карточки;
- создаёт integral readiness/opportunity/card score, которого нет в domain;
- показывает invented data/forecast ради заполнения макета;
- использует category-wide benchmark там, где продукт требует selected competitors;
- делает MPStats/Ozon source concepts частью визуального языка без необходимости;
- использует color-only status;
- прячет freshness/period/active query;
- заменяет insufficient-data красивым пустым chart;
- показывает spinner без понятного состояния длительной операции;
- требует remote font/CDN для нормального внешнего вида;
- ломается при 125–150% Windows scaling;
- требует page-level horizontal scroll на основном analytical screen при нормальном desktop viewport.

---

## 23. Implementation contract

Visual system должен быть реализован как небольшая система reusable primitives, а не набор случайных styles на страницах.

Минимальный принцип:

```text
Design tokens
  → App shell/layout
  → Buttons / Inputs / Tabs / Chips
  → Card / Banner / Empty-State primitives
  → Table primitives
  → Chart styling helpers
  → Feature screens
```

Design tokens — CSS custom properties или эквивалентный единый механизм.

Feature screen не должен самостоятельно придумывать:

- новые primary colors;
- новый radius;
- новую button hierarchy;
- новый status treatment;
- новую typography scale.

При этом не требуется строить отдельный enterprise component library, Storybook или design-system package до появления реальной необходимости. Shared components внутри frontend достаточно.

---

## 24. Definition of Done визуального слоя

Visual foundation считается соответствующим SCOZ, когда:

- приложение выглядит как единый современный продукт, а не набор независимых страниц;
- глобальная IA и Product Workspace не содержат придуманных разделов;
- page hierarchy считывается за несколько секунд;
- primary action визуально одна на смысловой block;
- таблицы читаемы и плотны без ощущения Excel/BI-конструктора;
- карточки используются осмысленно и не создают tile-wall;
- semantic colors спокойные и не являются единственным носителем состояния;
- charts минималистичны и честно отражают analytical model;
- loading/empty/error/stale/insufficient states выглядят как часть продукта;
- offline внешний вид не зависит от remote fonts/CDN;
- Windows scaling 125–150% не разрушает layout;
- интерфейс соответствует UX North Star: пользователь понимает контекст, действие, результат и ограничение данных.

---

## 25. Главный визуальный критерий

Если есть выбор между «эффектнее» и «яснее», выбирать **яснее**.

Если есть выбор между ещё одной карточкой и хорошо структурированным общим блоком, выбирать **структуру**.

Если есть выбор между декоративным графиком и понятной таблицей, выбирать то, что быстрее отвечает на бизнес-вопрос.

Итоговый визуальный характер SCOZ:

> **спокойный, современный, профессиональный аналитический инструмент с высокой информационной плотностью, но без визуального шума.**
