from io import BytesIO
from typing import Mapping, Sequence

from openpyxl import Workbook


OZON_PRODUCTS_HEADERS = (
    "Название товара",
    "Ссылка на товар",
    "Продавец",
    "Бренд",
    "Категория 1 уровня",
    "Категория 3 уровня",
    "Признак товара",
    "Заказано на сумму, ₽",
    "Динамика оборота, %",
    "Заказано, штуки",
    "Средняя цена, ₽",
    "Минимальная цена, ₽",
    "Доля выкупа, %",
    "Упущенные продажи",
    "Дней без остатка",
    "Среднесуточные продажи, ₽",
    "Среднесуточные продажи, штуки",
    "Остаток на конец периода, штуки",
    "Схема работы",
    "Объем товара, л",
    "Показы всего",
    "Просмотры в поиске и каталоге",
    "Просмотры карточки",
    "Конверсия из показа в заказ, %",
    "В корзину из поиска и каталога, %",
    "В корзину из карточки, %",
    "Скидка за счет акций",
    "Доля суммы заказов по акциям, %",
    "Дней в акциях",
    "Дней с продвижением",
    "Доля рекламных расходов, %",
    "Дата создания карточки товара",
)

OZON_SEARCH_VISIBILITY_HEADERS = (
    "Позиция", "ID товара", "Название товара", "Имя селлера", "Сводная оценка",
    "Статус", "Ставка\nОплата за клик", "Стратегия",
    "Ставка\nОплата за заказ", "Соответствие запросу", "Отзывы",
    "Цена для покупателя", "Популярность общая", "Акции от Ozon",
    "Срок доставки", "Индекс цен",
)


def _default_search_visibility_row() -> dict[str, object]:
    return dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, (
        "1", 100000001, "Синтетический товар", "Синтетический продавец", "0,526",
        "Продвигается", "10,50 ₽", "Автостратегия", "5%", "99,1",
        "4,8 (1 234 шт.)", "1 999 ₽", "42,2", "Да", "1-2 дня", "10,0%",
    ), strict=True))


def build_ozon_search_visibility_workbook(
    *, query: str = "тестовый запрос", cluster: str = "г. Тестоград, Россия",
    date: str = "17/08/2026", time: str = "03:55 +00",
    declared_rows: int | None = None,
    rows: Sequence[Mapping[str, object]] | None = None,
    headers: Sequence[str] = OZON_SEARCH_VISIBILITY_HEADERS,
    extra_sheet: bool = False, merged_cells: Sequence[str] = (),
    formula_cells: Mapping[str, str] | None = None,
    q_z_values: Mapping[str, object] | None = None,
    row_6_values: Mapping[int, object] | None = None,
    row_8_values: Mapping[int, object] | None = None,
    row_9_values: Mapping[int, object] | None = None,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    source_rows = rows if rows is not None else (_default_search_visibility_row(),)
    declared = len(source_rows) if declared_rows is None else declared_rows
    for coordinate, value in {
        "A1": f"Дата: {date}", "A2": f"Запрос: {query}",
        "A3": f"Время: {time}", "A4": f"Регион: {cluster}",
        "A5": f"Сколько позиций в выдаче: {declared}",
    }.items():
        sheet[coordinate] = value
    for column, header in enumerate(headers, 1):
        sheet.cell(7, column, header)
    for column, value in (row_6_values or {}).items(): sheet.cell(6, column, value)
    for column, value in (row_8_values or {}).items(): sheet.cell(8, column, value)
    help_values = row_9_values or {1: "Синтетическая поясняющая строка"}
    for column, value in help_values.items(): sheet.cell(9, column, value)
    for row_number, row in enumerate(source_rows, 10):
        for column, header in enumerate(headers, 1):
            value = row.get(header)
            # openpyxl serializes 1.0 as the integer lexical form ``1``. Preserve
            # this deliberately invalid mutation so parser tests can distinguish it.
            if header == "ID товара" and isinstance(value, float):
                value = str(value)
            sheet.cell(row_number, column, value)
    for coordinate, value in (q_z_values or {}).items(): sheet[coordinate] = value
    for coordinate, value in (formula_cells or {}).items(): sheet[coordinate] = value
    for cell_range in merged_cells: sheet.merge_cells(cell_range)
    if extra_sheet: workbook.create_sheet()
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _default_row(category_level_3: str) -> dict[str, object]:
    return dict(zip(OZON_PRODUCTS_HEADERS, (
        "Синтетический товар",
        "https://www.ozon.ru/product/100000001/",
        "Синтетический продавец",
        "Синтетический бренд",
        "Синтетическая категория 1",
        category_level_3,
        None,
        1000,
        1.31,
        2,
        500,
        450,
        95.8,
        0,
        "0 из 28",
        0,
        0,
        0,
        "FBO",
        1.5,
        100,
        50,
        25,
        2.5,
        5.0,
        10.0,
        0,
        0,
        "0 из 7",
        "0 из 7",
        7.7,
        "2026-01-01",
    ), strict=True))


def build_ozon_products_workbook(
    *,
    rows: Sequence[Mapping[str, object]] | None = None,
    generated_on: str = "08.16.26",
    window_label: str = "7 дней",
    category_level_3: str = "Синтетическая категория",
    marker_overrides: Mapping[str, object] | None = None,
    headers: Sequence[str] = OZON_PRODUCTS_HEADERS,
    extra_sheet: bool = False,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    markers: dict[str, object] = {
        "A1": "Дата формирования:",
        "B1": generated_on,
        "A2": "Период отчета:",
        "B2": window_label,
        "A3": "Категория 3 уровня:",
        "B3": category_level_3,
        "A6": "Среднее значение по товарам",
    }
    markers.update(marker_overrides or {})
    for coordinate, value in markers.items():
        sheet[coordinate] = value
    sheet.append([])  # Rows 1-3 already exist; preserve blank contract row 4.
    for column, header in enumerate(headers, start=1):
        sheet.cell(row=5, column=column, value=header)
    source_rows = rows if rows is not None else (_default_row(category_level_3),)
    for row_number, row in enumerate(source_rows, start=7):
        for column, header in enumerate(headers, start=1):
            sheet.cell(row=row_number, column=column, value=row.get(header))
    if extra_sheet:
        workbook.create_sheet()
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()
