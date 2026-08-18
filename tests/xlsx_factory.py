from io import BytesIO
from typing import Mapping, Sequence

from openpyxl import Workbook
from openpyxl.styles import PatternFill


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
    "Позиция",
    "ID товара",
    "Название товара",
    "Имя селлера",
    "Сводная оценка",
    "Статус",
    "Ставка\nОплата за клик",
    "Стратегия",
    "Ставка\nОплата за заказ",
    "Соответствие запросу",
    "Отзывы",
    "Цена для покупателя",
    "Популярность общая",
    "Акции от Ozon",
    "Срок доставки",
    "Индекс цен",
)


def _default_search_visibility_row() -> dict[str, object]:
    return dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, (
        "1",
        100000001,
        "Синтетический товар",
        "Синтетический продавец",
        "0,685",
        "Продвигается",
        "22,32 ₽",
        "Автостратегия",
        "10%",
        "84,10",
        "4,8 (180 шт.)",
        "2 947 ₽",
        "2,60",
        "Да",
        "1-2 дня",
        "5,0%",
    ), strict=True))


def build_ozon_search_visibility_workbook(
    *,
    query: str = "тестовый запрос",
    cluster: str = "г. Тестоград, Россия",
    date: str = "17/08/2026",
    time: str = "03:55 +00",
    declared_rows: int | None = None,
    headers: Sequence[str] = OZON_SEARCH_VISIBILITY_HEADERS,
    rows: Sequence[Mapping[str, object]] | None = None,
    extra_sheet: bool = False,
    row_6_values: Mapping[str, object] | None = None,
    row_8_values: Mapping[str, object] | None = None,
    row_9_values: Mapping[str, object] | None = None,
    merged_ranges: Sequence[str] = (),
    formula_cells: Mapping[str, str] | None = None,
    q_to_z_values: Mapping[str, object] | None = None,
    style_q_to_z: bool = True,
) -> bytes:
    """Build only synthetic examples of the frozen explainer_report shape."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Поисковая видимость"
    source_rows = tuple(rows) if rows is not None else (_default_search_visibility_row(),)
    count = len(source_rows) if declared_rows is None else declared_rows
    metadata = (
        f"Дата: {date}",
        f"Запрос: {query}",
        f"Время: {time}",
        f"Регион: {cluster}",
        f"Сколько позиций в выдаче: {count}",
    )
    for row_number, value in enumerate(metadata, start=1):
        sheet.cell(row=row_number, column=1, value=value)
    for column, header in enumerate(headers, start=1):
        sheet.cell(row=7, column=column, value=header)
    sheet["A9"] = "Справочная строка"
    for row_number, row in enumerate(source_rows, start=10):
        for column, header in enumerate(headers, start=1):
            sheet.cell(row=row_number, column=column, value=row.get(header))

    for row_number, mutations in (
        (6, row_6_values), (8, row_8_values), (9, row_9_values),
    ):
        for column, value in (mutations or {}).items():
            sheet[f"{column}{row_number}"] = value
    for coordinate, formula in (formula_cells or {}).items():
        sheet[coordinate] = formula
    for coordinate, value in (q_to_z_values or {}).items():
        sheet[coordinate] = value
    if style_q_to_z:
        fill = PatternFill(fill_type="solid", fgColor="FFFFFF")
        for column in range(17, 27):
            sheet.cell(row=10, column=column).fill = fill
    for cell_range in merged_ranges:
        sheet.merge_cells(cell_range)
    if extra_sheet:
        workbook.create_sheet("Лишний лист")
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
