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
