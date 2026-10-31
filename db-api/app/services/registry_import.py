"""Разбор банковского реестра участков (.xlsx)."""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

HEADER_ALIASES = {
    "территория": "address",
    "адрес": "address",
    "кадастровый номер": "cadastral_number",
    "кадастр": "cadastral_number",
    "плановая дата": "planned_completion_at",
    "плановое завершение": "planned_completion_at",
    "дата начала строительства": "credit_issued_at",
    "дата выдачи кредита": "credit_issued_at",
    "название": "name",
    "объект": "name",
    "материал": "material",
    "широта": "lat",
    "долгота": "lon",
}

EMPTY_MARKERS = {"", "нет", "нет данных", "-", "—", "n/a", "na"}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").replace("ё", "е").replace("Ё", "е").lower().split())


def _cell(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def parse_date(value: Any) -> date | None:
    value = _cell(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return from_excel(value).date()
    text = str(value).strip()
    if _norm(text) in EMPTY_MARKERS:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Непонятная дата: {value}")


def default_name(address: str, cadastral: str) -> str:
    parts = [part.strip() for part in address.replace(";", ",").split(",") if part.strip()]
    if len(parts) >= 2:
        return ", ".join(parts[-2:])[:255]
    if parts:
        return parts[0][:255]
    return f"Участок {cadastral}"


def _map_headers(row: tuple[Any, ...]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for idx, raw in enumerate(row):
        key = HEADER_ALIASES.get(_norm(raw))
        if key:
            mapping[idx] = key
    return mapping


def parse_registry(content: bytes, filename: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Нужен файл Excel в формате .xlsx")
    try:
        wb = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError("Не удалось прочитать Excel") from exc

    ws = wb.active
    header_map: dict[int, str] = {}
    header_row = 0
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, raw in enumerate(ws.iter_rows(values_only=True), start=1):
        if not header_map:
            candidate = _map_headers(raw)
            if {"address", "cadastral_number"} <= set(candidate.values()):
                header_map = candidate
                header_row = index
            elif index >= 10:
                raise ValueError("В файле нет колонок «Территория» и «Кадастровый номер»")
            continue

        values = {field: _cell(raw[col]) if col < len(raw) else None for col, field in header_map.items()}
        if all(values.get(field) in (None, "") for field in ("address", "cadastral_number", "name")):
            continue

        cadastral = str(values.get("cadastral_number") or "").strip()
        address = str(values.get("address") or "").strip()
        try:
            if not cadastral:
                raise ValueError("Нет кадастрового номера")
            if not address:
                raise ValueError("Нет территории / адреса")
            credit = parse_date(values.get("credit_issued_at"))
            planned = parse_date(values.get("planned_completion_at"))
            if credit is None:
                raise ValueError("Нет даты начала строительства")
            if planned is None:
                raise ValueError("Нет плановой даты")
            if planned <= credit:
                raise ValueError("Плановая дата должна быть позже даты начала строительства")
            lat = values.get("lat")
            lon = values.get("lon")
            corners: list[dict[str, float]] = []
            if lat not in (None, "") and lon not in (None, ""):
                corners = [{"lat": float(lat), "lon": float(lon)}]
            material = str(values.get("material") or "иное").strip() or "иное"
            name = str(values.get("name") or "").strip() or default_name(address, cadastral)
            rows.append(
                {
                    "row": index,
                    "name": name,
                    "cadastral_number": cadastral,
                    "address": address,
                    "plot_corners": corners,
                    "credit_issued_at": credit,
                    "planned_completion_at": planned,
                    "material": material,
                }
            )
        except (TypeError, ValueError) as exc:
            errors.append({"row": index, "cadastral_number": cadastral, "error": str(exc)})

    wb.close()
    if not header_map:
        raise ValueError("В файле нет колонок «Территория» и «Кадастровый номер»")
    if not rows and not errors:
        raise ValueError("В реестре нет строк с объектами")
    if header_row and not rows and errors:
        return rows, errors
    return rows, errors
