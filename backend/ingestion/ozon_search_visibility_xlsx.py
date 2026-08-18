import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from backend.domain.search_visibility import (
    CpoState,
    ParsedSearchVisibilityReport,
    ParsedSearchVisibilityRow,
    SearchVisibilityConflictingObservationRows,
    SearchVisibilityIncompatibleReportSchema,
    SearchVisibilityInvalidObservedAt,
    SearchVisibilityInvalidSearchContext,
    SearchVisibilityRowError,
    SearchVisibilityUnsupportedWorkbook,
    SearchVisibilityWrongReportType,
    search_visibility_payload_sha256,
)


HEADERS = (
    "Позиция", "ID товара", "Название товара", "Имя селлера", "Сводная оценка", "Статус",
    "Ставка\nОплата за клик", "Стратегия", "Ставка\nОплата за заказ", "Соответствие запросу",
    "Отзывы", "Цена для покупателя", "Популярность общая", "Акции от Ozon", "Срок доставки", "Индекс цен",
)

_ERRORS = {
    "INVALID_PRODUCT_IDENTITY": "Некорректный ID товара.",
    "INVALID_POSITION": "Некорректная позиция товара.",
    "INVALID_METRIC_VALUE": "Некорректное значение показателя.",
    "INVALID_CPO_STATE": "Некорректное значение оплаты за заказ.",
    "INVALID_REVIEWS": "Некорректное значение отзывов.",
    "INVALID_DELIVERY": "Некорректный срок доставки.",
}


class _RowProblem(ValueError):
    def __init__(self, code: str):
        self.code = code


def _edge_cleanup_identity(value: str) -> str:
    return value.strip(" \u00a0")


def _semantically_blank(value: object) -> bool:
    return value is None or value == ""


def _formula_cell(cell) -> bool:
    return cell.data_type == "f"


def _parse_observed_at(date_text: str, time_text: str) -> datetime:
    if re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", date_text) is None or re.fullmatch(r"[0-9]{2}:[0-9]{2} \+00", time_text) is None:
        raise SearchVisibilityInvalidObservedAt()
    try:
        return datetime.strptime(f"{date_text} {time_text[:5]}", "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise SearchVisibilityInvalidObservedAt() from exc


def _parse_position(value: object) -> int:
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise _RowProblem("INVALID_POSITION")
    return int(value)


def _parse_product_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _RowProblem("INVALID_PRODUCT_IDENTITY")
    return str(value)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or value == "":
        raise _RowProblem("INVALID_METRIC_VALUE")
    return value


def _parse_decimal_comma(value: object) -> Decimal:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+,[0-9]+", value) is None:
        raise _RowProblem("INVALID_METRIC_VALUE")
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise _RowProblem("INVALID_METRIC_VALUE") from exc


def _grouped_digits(value: str) -> str | None:
    if re.fullmatch(r"[0-9]+", value):
        return value
    if re.fullmatch(r"[0-9]{1,3}(?: [0-9]{3})+", value):
        return value.replace(" ", "")
    return None


def _parse_cpc(value: object) -> Decimal:
    if not isinstance(value, str) or not (match := re.fullmatch(r"(.+),([0-9]{2}) ₽", value)):
        raise _RowProblem("INVALID_METRIC_VALUE")
    whole = _grouped_digits(match.group(1))
    if whole is None:
        raise _RowProblem("INVALID_METRIC_VALUE")
    return Decimal(f"{whole}.{match.group(2)}")


def _parse_cpo(value: object) -> tuple[CpoState, Decimal | None]:
    if value == "Выключено":
        return CpoState.DISABLED, None
    if value == "—":
        return CpoState.UNAVAILABLE, None
    if isinstance(value, str) and (match := re.fullmatch(r"([0-9]+)%", value)):
        return CpoState.ACTIVE, Decimal(match.group(1))
    raise _RowProblem("INVALID_CPO_STATE")


def _parse_reviews(value: object) -> tuple[Decimal | None, int | None]:
    if value == "— ":
        return None, None
    if isinstance(value, str) and (match := re.fullmatch(r"([0-9]+,[0-9]+) \((.+) шт\.\)", value)):
        count = _grouped_digits(match.group(2))
        if count is not None:
            return Decimal(match.group(1).replace(",", ".")), int(count)
    raise _RowProblem("INVALID_REVIEWS")


def _parse_buyer_price(value: object) -> Decimal:
    if not isinstance(value, str) or not value.endswith(" ₽"):
        raise _RowProblem("INVALID_METRIC_VALUE")
    digits = _grouped_digits(value[:-2])
    if digits is None:
        raise _RowProblem("INVALID_METRIC_VALUE")
    return Decimal(digits)


def _parse_delivery(value: object) -> tuple[str, int, int]:
    if not isinstance(value, str) or not (match := re.fullmatch(r"([0-9]+)-([0-9]+) (день|дня|дней)", value)):
        raise _RowProblem("INVALID_DELIVERY")
    minimum, maximum = int(match.group(1)), int(match.group(2))
    if minimum > maximum:
        raise _RowProblem("INVALID_DELIVERY")
    return value, minimum, maximum


def _parse_price_index(value: object) -> Decimal:
    if not isinstance(value, str) or not value.endswith("%"):
        raise _RowProblem("INVALID_METRIC_VALUE")
    return _parse_decimal_comma(value[:-1])


def _parse_product_row(cells) -> tuple[str, dict[str, object]]:
    if any(_formula_cell(cell) for cell in cells):
        raise _RowProblem("INVALID_METRIC_VALUE")
    values = [cell.value for cell in cells]
    product_id = _parse_product_id(values[1])
    cpo_state, cpo_pct = _parse_cpo(values[8])
    rating, reviews_count = _parse_reviews(values[10])
    delivery_label, delivery_min, delivery_max = _parse_delivery(values[14])
    if values[13] not in ("Да", "Нет"):
        raise _RowProblem("INVALID_METRIC_VALUE")
    payload = {
        "source_title": _required_text(values[2]), "seller_name": _required_text(values[3]),
        "position": _parse_position(values[0]), "overall_score": _parse_decimal_comma(values[4]),
        "promotion_status": _required_text(values[5]), "cpc_rub": _parse_cpc(values[6]),
        "promotion_strategy": _required_text(values[7]), "cpo_state": cpo_state,
        "cpo_pct": cpo_pct, "relevance_score": _parse_decimal_comma(values[9]),
        "rating": rating, "reviews_count": reviews_count,
        "buyer_price_rub": _parse_buyer_price(values[11]),
        "popularity_score": _parse_decimal_comma(values[12]),
        "ozon_promotion": values[13] == "Да", "delivery_label": delivery_label,
        "delivery_min_days": delivery_min, "delivery_max_days": delivery_max,
        "price_index_pct": _parse_price_index(values[15]),
    }
    return product_id, payload


def parse_ozon_search_visibility_xlsx(path: Path) -> ParsedSearchVisibilityReport:
    try:
        with zipfile.ZipFile(path) as package:
            worksheet_xml = [name for name in package.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            if any(b"<mergeCells" in package.read(name) for name in worksheet_xml):
                raise SearchVisibilityIncompatibleReportSchema()
    except SearchVisibilityIncompatibleReportSchema:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise SearchVisibilityUnsupportedWorkbook() from exc

    source = None
    workbook = None
    try:
        source = path.open("rb")
        workbook = load_workbook(filename=source, read_only=True, data_only=False)
        if len(workbook.worksheets) != 1:
            raise SearchVisibilityIncompatibleReportSchema()
        sheet = workbook.worksheets[0]
        if any(_formula_cell(sheet.cell(row=r, column=c)) for r in range(1, 10) for c in range(1, 17)):
            raise SearchVisibilityIncompatibleReportSchema()
        markers = tuple(sheet.cell(row=i, column=1).value for i in range(1, 6))
        prefixes = ("Дата: ", "Запрос: ", "Время: ", "Регион: ", "Сколько позиций в выдаче: ")
        if not isinstance(markers[0], str) or not markers[0].startswith(prefixes[0]):
            raise SearchVisibilityWrongReportType()
        if any(not isinstance(value, str) or not value.startswith(prefix) for value, prefix in zip(markers, prefixes, strict=True)):
            raise SearchVisibilityIncompatibleReportSchema()
        if any(not _semantically_blank(sheet.cell(row=r, column=c).value) for r in (6, 8) for c in range(1, 17)):
            raise SearchVisibilityIncompatibleReportSchema()
        if tuple(sheet.cell(row=7, column=c).value for c in range(1, 17)) != HEADERS:
            raise SearchVisibilityIncompatibleReportSchema()
        if any(not _semantically_blank(sheet.cell(row=r, column=c).value) for r in range(1, sheet.max_row + 1) for c in range(17, sheet.max_column + 1)):
            raise SearchVisibilityIncompatibleReportSchema()

        observed_at = _parse_observed_at(markers[0][len(prefixes[0]):], markers[2][len(prefixes[2]):])
        query = _edge_cleanup_identity(markers[1][len(prefixes[1]):])
        cluster = _edge_cleanup_identity(markers[3][len(prefixes[3]):])
        if not query or not cluster:
            raise SearchVisibilityInvalidSearchContext()
        declared_text = markers[4][len(prefixes[4]):]
        if re.fullmatch(r"[1-9][0-9]*", declared_text) is None:
            raise SearchVisibilityIncompatibleReportSchema()
        declared = int(declared_text)
        candidate_rows = [r for r in range(10, sheet.max_row + 1) if any(not _semantically_blank(sheet.cell(row=r, column=c).value) for c in range(1, 17))]
        if len(candidate_rows) != declared:
            raise SearchVisibilityIncompatibleReportSchema()

        rows = []
        errors = []
        seen: dict[str, str] = {}
        duplicates = 0
        for row_number in candidate_rows:
            try:
                product_id, payload = _parse_product_row(tuple(sheet.cell(row=row_number, column=c) for c in range(1, 17)))
                digest = search_visibility_payload_sha256(payload)
                if product_id in seen:
                    if seen[product_id] != digest:
                        raise SearchVisibilityConflictingObservationRows()
                    duplicates += 1
                    continue
                seen[product_id] = digest
                rows.append(ParsedSearchVisibilityRow(row_number, product_id, payload, digest))
            except _RowProblem as exc:
                errors.append(SearchVisibilityRowError(row_number, exc.code, _ERRORS[exc.code]))
        return ParsedSearchVisibilityReport(observed_at, query, cluster, declared, len(candidate_rows), tuple(rows), tuple(errors), duplicates, duplicates)
    except (SearchVisibilityWrongReportType, SearchVisibilityIncompatibleReportSchema, SearchVisibilityInvalidObservedAt, SearchVisibilityInvalidSearchContext, SearchVisibilityConflictingObservationRows):
        raise
    except Exception as exc:
        raise SearchVisibilityUnsupportedWorkbook() from exc
    finally:
        if workbook is not None:
            workbook.close()
        if source is not None:
            source.close()
