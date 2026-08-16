# Ozon «Товары на Ozon» XLSX — Source Contract v1

**Status:** Approved factual source contract v1

**Date:** 2026-08-16

**Scope:** only the verified Ozon «Товары на Ozon» XLSX shape described here

## 1. Authority and evidence provenance

This contract freezes the source facts established by direct inspection of the user-supplied workbook `analytics_report_2026-08-16_16_27.xlsx`. The workbook itself is sensitive user input and is **not stored, copied into fixtures, or committed to this repository**. Its evidence identifiers are:

- SHA-256: `0ec6ad1681d69456e169b619b92917b6b36c930cc91b86a86460aa00cafffdd1`;
- byte size: `234807`;
- one worksheet named `Sheet1`;
- 1,006 rows and 32 columns;
- 1,000 product rows;
- no merged cells and no formula cells.

The worksheet name and filename are evidence metadata, not report-detection inputs. Workbook created/modified metadata is technical metadata and is never business freshness.

## 2. Exact workbook structure

The sole worksheet has this fixed layout:

| Row | Contract |
|---|---|
| 1 | `A1 = "Дата формирования:"`; B1 is the generated-date value |
| 2 | `A2 = "Период отчета:"`; B2 is the report-window label |
| 3 | `A3 = "Категория 3 уровня:"`; B3 is the level-3 category metadata |
| 4 | every cell A:AF is blank |
| 5 | exact ordered header signature in A:AF |
| 6 | summary row; `A6 = "Среднее значение по товарам"` |
| 7..end | product rows |

The parser starts product-row semantics at row 7. Row 6 never creates a Product, ProductExternalIdentity, or ProductSnapshot. A completely blank trailing row is ignored; a row with any non-blank cell is a product-row candidate and is validated as such.

## 3. Exact ordered header signature

Aliases, reordering, fuzzy matching, normalization of header spelling, and invented optional variants are forbidden. A5:AF5 is exactly:

1. `Название товара`
2. `Ссылка на товар`
3. `Продавец`
4. `Бренд`
5. `Категория 1 уровня`
6. `Категория 3 уровня`
7. `Признак товара`
8. `Заказано на сумму, ₽`
9. `Динамика оборота, %`
10. `Заказано, штуки`
11. `Средняя цена, ₽`
12. `Минимальная цена, ₽`
13. `Доля выкупа, %`
14. `Упущенные продажи`
15. `Дней без остатка`
16. `Среднесуточные продажи, ₽`
17. `Среднесуточные продажи, штуки`
18. `Остаток на конец периода, штуки`
19. `Схема работы`
20. `Объем товара, л`
21. `Показы всего`
22. `Просмотры в поиске и каталоге`
23. `Просмотры карточки`
24. `Конверсия из показа в заказ, %`
25. `В корзину из поиска и каталога, %`
26. `В корзину из карточки, %`
27. `Скидка за счет акций`
28. `Доля суммы заказов по акциям, %`
29. `Дней в акциях`
30. `Дней с продвижением`
31. `Доля рекламных расходов, %`
32. `Дата создания карточки товара`

## 4. Deterministic report detection

`report_type = OZON_PRODUCTS` only when all of the following hold: A1, A2, and A3 equal the exact markers above; A4:AF4 is blank; A5:AF5 equals the signature above; and A6 equals the exact summary marker. A readable workbook whose markers identify another report is `WRONG_REPORT_TYPE`; a workbook with the expected three markers but a wrong blank row, header signature, column count, sheet count, or summary marker is `INCOMPATIBLE_SCHEMA`. An unreadable/non-XLSX package is `UNSUPPORTED_WORKBOOK`.

Detection never uses filename, worksheet name, or fuzzy similarity and never guesses a near match.

## 5. Report period and freshness

B1 is text in exact v1 format `MM.DD.YY`. The observed value `08.16.26` normalizes to `report_generated_on = 2026-08-16`. B2 is exact text matching `^([1-9][0-9]*) дней$`; the observed `7 дней` normalizes to `report_window_days = 7`.

The workbook supplies neither `period_start` nor `period_end`. They must not be inferred from the generated date or window. The canonical UI phrase is `7 дней · отчёт сформирован 16.08.2026`, never an invented date range. Freshness uses `report_generated_on`; import time is a separate application fact.

## 6. Product identity and ownership boundary

`Ссылка на товар` has exact supported pattern `^https://www\.ozon\.ru/product/(\d+)/?$`. Its decimal capture is preserved as a canonical digit string and maps to:

- `source = "ozon"`;
- `identity_type = "ozon_product_id"`;
- `identity_value = <captured digits>`;
- `source_account_scope = ""`.

The normalized `product_url` is the canonical no-trailing-slash URL reconstructed from that identity. Seller offer ID is absent. Title, brand, seller, category, photo, and URL text outside this exact extraction rule are not identity; the evidence includes equal titles with different product IDs. The report has no reliable own/competitor flag, so it cannot set ownership. `Product.is_owned` is managed manually after import and multiple owned products are valid.

## 7. Cell types, numeric representation, and units

Source money, count, percentage/ratio, and physical values in the verified workbook are real Excel numeric cells (`int`/`float` as exposed by `openpyxl`), not localized numeric strings. A formula in any product metric cell is unsupported and is an invalid row; formulas in structure/metadata cells make the workbook incompatible. Boolean values are not numeric despite Python's type hierarchy. Numeric zero is an observed fact and never means missing. There is no generic truthiness-to-null rule.

Semantic classes are:

| Class | Headers | Normalized semantics |
|---|---|---|
| RUB money | `Заказано на сумму, ₽`, `Средняя цена, ₽`, `Минимальная цена, ₽`, `Среднесуточные продажи, ₽` | exact decimal rubles |
| Counts | `Заказано, штуки`, `Среднесуточные продажи, штуки`, `Остаток на конец периода, штуки`, `Показы всего`, `Просмотры в поиске и каталоге`, `Просмотры карточки` | non-negative whole-number counts |
| Physical | `Объем товара, л` | exact decimal litres |
| Percentage points | the seven headers in section 8 | exact decimal percentage points |
| Windowed days | the three day headers in section 10 | explicit integer numerator and denominator |
| Raw numeric, unit unconfirmed | `Упущенные продажи`, `Скидка за счет акций` | exact source decimal only; no currency/percent label or analytical interpretation |

The evidence confirms numeric behavior for `Упущенные продажи` and `Скидка за счет акций`, but their headers and supplied evidence do not establish a unit. Therefore v1 deliberately names them `missed_sales_source_value` and `promotion_discount_source_value`; neither may be displayed with `₽`/`%`, recomputed, or used by analytics. This is a fixed conservative v1 behavior, not an implementation choice.

All non-window numeric metrics require finite values. Counts and day components require mathematically integral, non-negative values. Money, percentage points, volume, and raw numeric values normalize through exact decimal conversion of the Excel cell's lexical decimal representation; NaN and infinities are invalid.

## 8. Percentage-point contract

Excel percentage formatting is not used. The source numeric value is already percentage points and is neither multiplied nor divided by 100. Thus `1.31` means `1.31%`, `95.8` means `95.8%`, and `7.7` means `7.7%`. This applies exactly to:

- `Динамика оборота, %` → `turnover_change_pct`;
- `Доля выкупа, %` → `buyout_share_pct`;
- `Конверсия из показа в заказ, %` → `impression_to_order_pct`;
- `В корзину из поиска и каталога, %` → `search_catalog_to_cart_pct`;
- `В корзину из карточки, %` → `card_to_cart_pct`;
- `Доля суммы заказов по акциям, %` → `promotion_order_amount_share_pct`;
- `Доля рекламных расходов, %` → `total_drr_pct`.

`total_drr_pct` is the observed Ozon DRR fact. For example, `7.7` remains `7.7`; it is not stored as `0.077` and is not recomputed.

## 9. Exact missing sentinels

- `Динамика оборота, %`: numeric, or exact string `Нет данных` → `None`.
- `Доля выкупа, %`: numeric, or exact string `Нет данных` → `None`.
- `Дней без остатка`: exact window form, or exact string `-` → both normalized fields `None`; this is unknown, not zero.
- `Признак товара`: blank Excel cell (`None`) → `product_badges = None`; otherwise its source text is preserved without treating an empty/falsy numeric value as missing.

No other metric accepts those sentinels. An unexpected blank or string in a required numeric metric is invalid. Explicit numeric `0` remains zero in every numeric field.

## 10. Windowed-day semantics

These text cells match exact pattern `^([0-9]+) из ([1-9][0-9]*)$`, with numerator not exceeding denominator:

- `Дней без остатка` → `out_of_stock_days`, `out_of_stock_window_days`; observed denominator is 28;
- `Дней в акциях` → `promotion_days`, `promotion_window_days`; observed denominator is 7;
- `Дней с продвижением` → `advertising_days`, `advertising_window_days`; observed denominator is 7.

For example, `1 из 28` becomes `(1, 28)`. The explicit denominator is always retained. `report_window_days` is never substituted for it. Only `Дней без остатка` accepts `-`; the other two fields require their window form, including the valid explicit zero form `0 из 7`.

## 11. Dates, text, and row consistency

`Дата создания карточки товара` is source text in exact `YYYY-MM-DD` format and normalizes to a calendar date; Excel serial dates/datetimes are invalid. Title, seller, brand, both categories, fulfillment scheme, and product URL are source text. Required text is non-blank after rejecting truly empty cells; v1 does not perform fuzzy cleanup.

B3 is required non-empty category metadata. Every non-empty product row must have `Категория 3 уровня` exactly equal to B3. A mismatch is a row validation error, not identity and not a fatal structural error by itself. The verified workbook satisfies this for all 1,000 product rows.

## 12. Known invariants

- Exactly one worksheet, 32 columns, and the exact rows 1–6 structure are required.
- There are no merged or formula cells in the evidence workbook.
- Row 6 is summary-only; product observations begin at row 7.
- The report-level window and windowed-day metric denominators are distinct facts.
- Product identity is only the numeric Ozon product ID extracted from the exact URL.
- Source columns are facts. Parsing may normalize, split explicit numerator/denominator, and map identity; it must not recalculate turnover, conversions, daily sales, or DRR.
- Category is a consistency dimension, never identity or logical-key material.

## 13. Unsupported / not yet confirmed

The following are explicitly rejected by v1 rather than treated as implementation work to infer:

- alternative headers, aliases, header order, or spelling;
- alternative worksheet structures, shifted rows, merged cells, or extra columns;
- multiple sheets;
- formula-based exports;
- localized numeric strings such as `1 234,56`;
- different Ozon report/export versions;
- different period metadata formats;
- alternative product URL hosts, paths, query strings, or offer-ID identity;
- Excel serial/datetime card-creation values;
- other missing sentinels;
- an analytical or display unit for `Упущенные продажи` and `Скидка за счет акций`.

## 14. Compatibility and versioning policy

This is strict Source Contract v1 for the evidenced artifact shape. A workbook is compatible only when it passes deterministic v1 detection and field contracts. Any Ozon export change requires new factual evidence and a separately approved source-contract revision; code must not silently broaden v1. Rejection of an unsupported variant is correct compatibility behavior, not a fallback opportunity.
