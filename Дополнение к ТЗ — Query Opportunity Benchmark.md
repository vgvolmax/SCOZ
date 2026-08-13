# Дополнение к ТЗ — Query Opportunity Benchmark

## 1. Задача

Query Opportunity помогает понять, **по каким поисковым запросам сокращение разрыва с выбранными конкурентами действительно имеет коммерческий смысл**.

Это не отдельный BI-раздел. Он используется внутри `Product Workspace → Поиск` и как вход для режима «Разгон».

## 2. Четыре блока

- **Query Demand** — объём спроса.
- **Query Quality** — качество коммерческого интента.
- **Visibility Gap** — разрыв own SKU с выбранными competitors по позиции.
- **Position Stability** — устойчивость присутствия в TOP-N.

В v1 не создавать Opportunity Score 0–100. Verdict должен быть explainable.

## 3. Источники

Ozon query metrics используются для frequency/popularity, market CR, доли без действий, orders/turnover и других market-level signals.

MPStats используется для истории поисковых позиций own SKU и выбранных competitors:

> `business date × product × search query × position`

MPStats sales estimates не подменяют Ozon commercial benchmark.

Market query CR характеризует query intent и **не является CR конкретного competitor SKU**.

## 4. Granularity

Основная единица Query Opportunity:

> **Own SKU × Search Query × Period**

Cluster используется в следующем уровне Search Visibility drill-down, но не является обязательной dimension Query Opportunity.

Не смешивать query-level, cluster-level и aggregate metrics без явного корректного преобразования.

## 5. Demand и Quality

Высокая frequency сама по себе не означает высокий потенциал.

Приоритет может быть ниже у частотного query с низкой market CR и высокой долей поисков без действий, чем у менее частотного, но более коммерческого query.

## 6. Visibility Gap

Для query сравнивать own position с валидными observations членов сохранённой benchmark-группы.

Использовать при достаточных данных:

- current/median own position;
- median competitor position;
- P25/P75 только при достаточной sample;
- position gap;
- долю competitors выше own SKU.

Position — порядковая шкала; искусственный процент gap не обязателен.

Missing observation, unknown/null и подтверждённое отсутствие в диапазоне — разные состояния.

## 7. Position Stability / Share of Top

Минимально:

- Share of TOP-10;
- Share of TOP-20.

Каждая метрика возвращает denominator/sample size и period.

До реализации PR10 обязан проверить реальный MPStats contract: порядок массива относительно дат, missing calendar days, `null` semantics и business-date semantics.

До подтверждения `null` означает unknown observation, а не позицию 0/1000+.

## 8. UX

Перед cluster heatmap показывать компактный список:

| Query | Demand | Market quality | Мы | Benchmark | Verdict |
|---|---:|---:|---:|---:|---|

По клику query становится активным контекстом и открывается существующая heatmap:

> `Кластер | Позиция | Релевантность | Популярность | Доставка | Цена`

Не создавать отдельный глобальный Query Opportunity dashboard.

## 9. Связь с «Разгоном»

Query Opportunity отвечает, **по какому query вообще стоит рассматривать покупку более высокой позиции**.

Ramp-up затем работает на максимально детальной **общей** granularity реально доступных position/conversion/advertising inputs.

Базовый практический уровень:

> **SKU × query × time**

Cluster добавляется только при совместимых cluster-level inputs. Нельзя искусственно создавать cluster-level Ramp-up из query-level history.

Хороший кандидат: низкая позиция + нормальная position-normalized CR + хороший query intent + устойчивый competitor gap + достаточный demand.

## 10. Запреты

Не восстанавливать без прямого source evidence точные competitor impressions по query; не объявлять market query CR конверсией competitor; не использовать aggregate product CR как query-position CR; не превращать missing position в zero; не использовать MPStats sales estimates вместо Ozon metrics; не создавать ложную granularity.

## 11. Архитектура

Модуль `analytics/query_opportunity` получает нормализованные `QueryMetricSnapshot`, `SearchPositionSnapshot`, benchmark revision/members и own product/query context.

`analytics/search_visibility` отвечает **почему по выбранному query/cluster мы стоим хуже**, а Query Opportunity — **какой query разбирать в первую очередь**.

## 12. Acceptance criteria

Система показывает Demand/Quality, own и benchmark position, Share of Top с denominator и explainable verdict; high-frequency low-quality query может иметь низкий приоритет; missing observations обрабатываются явно; клик по query ведёт в существующую heatmap; модуль не использует MPStats competitor sales estimates и не создаёт cluster-level Ramp-up без cluster-level evidence.