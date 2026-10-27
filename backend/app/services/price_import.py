"""Secure, independently mapped import of supplier and central-price workbooks.

This service never writes to the database. All indices in a mapping/header are
zero-based; source_row is the one-based number shown in Excel. Decimal parsing
never rounds or silently inserts missing prices. A lone comma/dot denotes a
decimal separator; mixed separators require conventional thousands grouping.
Legacy .xls parsing is isolated through xlrd and never executes Excel macros.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata
from typing import Any, Callable
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from defusedxml.common import DefusedXmlException

from pydantic import ValidationError

from ..schemas import PriceInput
from .excel import _open, MAX_UPLOAD_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_CELLS

HEADER_SCAN_ROWS = 50
PREVIEW_ROWS = 60
MAX_IMPORT_ROWS = 10000
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def normalize_header(value: Any) -> str:
    """Normalize case, accents, BOM, Unicode spacing, punctuation and underscores."""
    text = unicodedata.normalize(
        "NFKD", str(value or "").replace("\ufeff", "")
    ).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[\W_]+", " ", text, flags=re.UNICODE).split())


_ALIASES = {
    "code": [
        "kodi",
        "kod",
        "nr",
        "no",
        "item code",
        "product code",
        "sku",
        "kodi i artikullit",
    ],
    "name": [
        "emertimi",
        "emërtimi",
        "pershkrimi",
        "përshkrimi",
        "artikulli",
        "zeri",
        "zëri",
        "emri",
        "item name",
        "product name",
        "emertimi i artikullit",
    ],
    "description": [
        "pershkrim",
        "përshkrim",
        "description",
        "work description",
        "standard description",
        "pershkrim i standardizuar",
        "pershkrimi i punimeve",
    ],
    "unit": [
        "njesia",
        "njësia",
        "njesi",
        "njësi",
        "unit",
        "uom",
        "nj",
        "nj mat",
        "nj matese",
        "njesia matese",
        "unit of measurement",
    ],
    "price": [
        "cmimi",
        "çmimi",
        "cmimi_njesi",
        "çmimi_njësi",
        "price",
        "unit_price",
        "unit price",
        "cmimi per njesi",
        "cmimi i njesise",
        "rate",
    ],
    "currency": ["monedha", "valuta", "currency code"],
    "synonyms": ["sinonime", "sinonimet", "emertime alternative", "alternative names"],
    "technical_specs": [
        "specifikime",
        "specifikimet",
        "specifikime teknike",
        "technical specifications",
    ],
    "category": ["kategoria", "kategori"],
    "subcategory": ["nenkategoria", "nënkategoria", "nenkategori", "subcategory"],
    "price_kind": ["lloji i cmimit", "lloji cmimit", "price type"],
    "supply_included": [
        "furnizimi i perfshire",
        "furnizimi perfshire",
        "supply included",
    ],
    "installation_included": [
        "montimi i perfshire",
        "instalimi i perfshire",
        "installation included",
    ],
    "supplier": ["furnitori", "furnizuesi"],
    "price_date": ["data e cmimit", "data cmimit"],
    "valid_until": ["vlefshmeria", "i vlefshem deri", "validity", "valid to"],
    "vat_included": ["tvsh e perfshire", "me tvsh", "vat included"],
    "vat_rate": ["norma tvsh", "tvsh", "tvsh %", "vat rate", "vat percent"],
    "material_cost": [
        "kosto materiali",
        "kosto materialesh",
        "kosto materialeve",
        "material cost",
    ],
    "labor_cost": ["kosto pune", "kosto punes", "labor cost", "labour cost"],
    "machinery_cost": [
        "kosto makinerish",
        "kosto makinerive",
        "machinery cost",
        "equipment cost",
    ],
    "transport_cost": [
        "kosto transporti",
        "kosto transportit",
        "transport cost",
        "transportation cost",
    ],
    "other_cost": ["kosto te tjera", "other direct costs"],
    "notes": ["shenime", "shënime", "komente"],
    "active": ["aktiv", "aktive", "status aktiv", "is active"],
    "reason": ["arsye", "arsyeja", "reason for change"],
}
# Canonical export names always take precedence. The explicit Albanian aliases
# above intentionally distinguish "pershkrimi" (name) from "pershkrim" (description).
_HEADER_FIELDS = {normalize_header(field): field for field in PriceInput.model_fields}
for _field, _names in _ALIASES.items():
    for _name in _names:
        _HEADER_FIELDS.setdefault(normalize_header(_name), _field)

_NUMERIC_FIELDS = {
    "price",
    "material_cost",
    "labor_cost",
    "machinery_cost",
    "transport_cost",
    "other_cost",
    "vat_rate",
}
_BOOLEAN_FIELDS = {"supply_included", "installation_included", "vat_included", "active"}
_DATE_FIELDS = {"price_date", "valid_until"}
_SUBTOTAL = re.compile(
    r"^(?:nen\s*total|subtotal|sub total|totali?|grand total|gjithsej|permbledhje|summary)(?:\b|:)"
)


@dataclass
class _Sheet:
    name: str
    row_count: int
    column_count: int
    rows: Callable[[], Any]


@dataclass
class _Book:
    sheets: list[_Sheet]
    close: Callable[[], None]


def _open_catalog(data: bytes, filename: str) -> _Book:
    if not isinstance(data, bytes) or not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Skedari është bosh ose tejkalon kufirin 20 MB")
    suffix = (
        filename.rsplit(".", 1)[-1].lower()
        if isinstance(filename, str) and "." in filename
        else ""
    )
    if suffix in {"xlsx", "xlsm"}:
        try:
            workbook = _open(data)
        except ValueError:
            raise
        except Exception as exc:
            # Parser diagnostics can include cell contents. Return a fixed error.
            raise ValueError("Skedar Excel i pavlefshëm ose i dëmtuar") from exc
        return _Book(
            [
                _Sheet(
                    sheet.title,
                    sheet.max_row,
                    sheet.max_column,
                    lambda sheet=sheet: sheet.iter_rows(values_only=True),
                )
                for sheet in workbook.worksheets
            ],
            workbook.close,
        )
    if suffix != "xls":
        raise ValueError("Përdorni skedar .xlsx, .xlsm ose .xls")
    if not data.startswith(OLE_SIGNATURE):
        raise ValueError(
            "Formati .xls duhet të jetë skedar binar OLE; për .xlsx përdorni prapashtesën përkatëse"
        )
    try:
        import xlrd
    except ImportError as exc:
        raise ValueError("Mbështetja .xls kërkon instalimin e xlrd") from exc
    workbook = None
    try:
        workbook = xlrd.open_workbook(
            file_contents=data,
            on_demand=True,
            ragged_rows=True,
            formatting_info=False,
            ignore_workbook_corruption=False,
        )
        if workbook.nsheets < 1 or workbook.nsheets > 100:
            raise ValueError("Numër i pavlefshëm fletësh Excel")
        sheets = []
        for index in range(workbook.nsheets):
            worksheet = workbook.sheet_by_index(index)
            if worksheet.nrows > MAX_ROWS or worksheet.ncols > MAX_COLUMNS:
                raise ValueError("Excel tejkalon kufirin e rreshtave ose kolonave")

            def legacy_rows(worksheet=worksheet):
                for number in range(worksheet.nrows):
                    values = []
                    for cell in worksheet.row(number):
                        if cell.ctype == xlrd.XL_CELL_BOOLEAN:
                            values.append(bool(cell.value))
                        elif cell.ctype == xlrd.XL_CELL_DATE:
                            try:
                                values.append(
                                    xlrd.xldate_as_datetime(
                                        cell.value, workbook.datemode
                                    )
                                )
                            except (ValueError, OverflowError, xlrd.XLDateError):
                                values.append("#INVALID_DATE")
                        elif cell.ctype == xlrd.XL_CELL_ERROR:
                            values.append(
                                xlrd.error_text_from_code.get(
                                    cell.value, "#EXCEL_ERROR"
                                )
                            )
                        else:
                            values.append(cell.value)
                    yield values

            sheets.append(
                _Sheet(worksheet.name, worksheet.nrows, worksheet.ncols, legacy_rows)
            )
        if sum(sheet.row_count * sheet.column_count for sheet in sheets) > MAX_CELLS:
            raise ValueError("Excel tejkalon kufirin total të qelizave")
        return _Book(sheets, workbook.release_resources)
    except ValueError:
        if workbook is not None:
            workbook.release_resources()
        raise
    except Exception as exc:
        if workbook is not None:
            workbook.release_resources()
        raise ValueError(
            "Skedar .xls i pavlefshëm, i dëmtuar ose i enkriptuar"
        ) from exc


def _suggest(cells) -> tuple[dict, dict]:
    columns: dict[str, list[int]] = {}
    for index, value in enumerate(cells):
        field = _HEADER_FIELDS.get(normalize_header(value))
        if field:
            columns.setdefault(field, []).append(index)
    ambiguous = {
        field: indices for field, indices in columns.items() if len(indices) > 1
    }
    return {
        field: indices[0] for field, indices in columns.items() if len(indices) == 1
    }, ambiguous


def _sheet_info(sheet: _Sheet) -> dict:
    preview = []
    candidates = []
    for index, cells in enumerate(sheet.rows()):
        if index >= PREVIEW_ROWS:
            break
        preview.append(
            [
                value.isoformat()
                if isinstance(value, (datetime, date))
                else str(value)
                if isinstance(value, float) and not math.isfinite(value)
                else value
                for value in cells
            ]
        )
        if index < HEADER_SCAN_ROWS:
            mapping, ambiguous = _suggest(cells)
            fields = set(mapping) | set(ambiguous)
            score = (
                len(fields)
                + 3 * ("unit" in fields)
                + 3 * ("price" in fields)
                + 2 * bool(fields & {"name", "description"})
            )
            candidates.append((score, index, mapping, ambiguous))
    _, header, mapping, ambiguous = max(
        candidates, key=lambda candidate: candidate[0], default=(0, 0, {}, {})
    )
    warnings = []
    if ambiguous:
        warnings.append(
            "Kolona të paqarta: zgjidhni hartëzim manual për fushat e përsëritura."
        )
    if not {"unit", "price"}.issubset(mapping) or not (
        {"name", "description"} & set(mapping)
    ):
        warnings.append(
            "Hartoni emërtimin ose përshkrimin, njësinë dhe çmimin para importit."
        )
    return {
        "name": sheet.name,
        "preview": preview,
        "header_row": header,
        "suggested_mapping": mapping,
        "ambiguous_headers": ambiguous,
        "row_count": sheet.row_count,
        "column_count": sheet.column_count,
        "mapping_required": bool(warnings),
        "warnings": warnings,
    }


def inspect_prices(data: bytes, filename: str) -> dict:
    workbook = _open_catalog(data, filename)
    try:
        if not workbook.sheets:
            raise ValueError("Skedari nuk përmban fletë pune")
        return {
            "sheets": [_sheet_info(sheet) for sheet in workbook.sheets],
            "default_sheet": workbook.sheets[0].name,
        }
    except (ParseError, DefusedXmlException, BadZipFile, EOFError) as exc:
        raise ValueError("Përmbajtja Excel është e dëmtuar ose e pasigurt") from exc
    finally:
        workbook.close()


def _blank(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, str)
        and not value.replace("\ufeff", "").strip()
    )


def _text(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("Kërkohet tekst, jo vlerë logjike")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _number(value: Any, places: int = 6) -> Decimal:
    if isinstance(value, bool) or isinstance(value, (datetime, date)) or _blank(value):
        raise ValueError(
            "Kërkohet numër jo negativ; vlera bosh nuk zëvendësohet me zero"
        )
    raw = str(value).strip()
    if any(char.isspace() for char in raw) and not re.fullmatch(
        r"[+-]?\d{1,3}(?:\s+\d{3})+(?:[.,]\d+)?", raw
    ):
        raise ValueError("Format i paqartë ndarësish të mijësheve")
    raw = "".join(char for char in raw if not char.isspace())
    if "," in raw and "." in raw:
        decimal_mark = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_mark == "," else ","
        whole, fraction = raw.rsplit(decimal_mark, 1)
        if (
            decimal_mark in whole
            or not re.fullmatch(
                r"[+-]?\d{1,3}(?:" + re.escape(thousands) + r"\d{3})+", whole
            )
            or not fraction.isdigit()
        ):
            raise ValueError(
                "Format i paqartë numri; kontrolloni ndarësit dhjetorë dhe të mijësheve"
            )
        raw = whole.replace(thousands, "") + "." + fraction
    elif raw.count(",") > 1 or raw.count(".") > 1:
        separator = "," if "," in raw else "."
        if not re.fullmatch(
            r"[+-]?\d{1,3}(?:" + re.escape(separator) + r"\d{3}){2,}", raw
        ):
            raise ValueError("Format i paqartë numri; kontrolloni ndarësit e mijësheve")
        raw = raw.replace(separator, "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?", raw):
        raise ValueError("Kërkohet numër i vlefshëm pa simbole monedhe")
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Kërkohet numër i vlefshëm") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1000000000000"):
        raise ValueError(
            "Numri duhet të jetë i fundëm, jo negativ dhe brenda kufirit të lejuar"
        )
    if result.as_tuple().exponent < -places:
        raise ValueError(
            f"Lejohen maksimumi {places} shifra pas presjes; çmimi nuk rrumbullakohet automatikisht"
        )
    return result


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)) and value in (0, 1):
        return bool(value)
    text = normalize_header(value)
    if text in {"true", "yes", "po", "1", "aktiv", "aktive"}:
        return True
    if text in {"false", "no", "jo", "0", "inaktiv", "joaktiv"}:
        return False
    raise ValueError("Përdorni Po/Jo, True/False ose 1/0")


def _validate_mapping(mapping: dict, column_count: int) -> dict:
    if not isinstance(mapping, dict):
        raise ValueError("Hartëzimi duhet të jetë objekt fushë-kolonë")
    if any(
        field not in PriceInput.model_fields
        or not isinstance(index, int)
        or isinstance(index, bool)
        or index < 0
        or index >= column_count
        for field, index in mapping.items()
    ):
        raise ValueError(
            "Hartëzim i pavlefshëm: përdorni fusha të çmimeve dhe kolona ekzistuese me indeks zero"
        )
    if len(set(mapping.values())) != len(mapping):
        raise ValueError(
            "Çdo kolonë mund të hartohet vetëm një herë; emërtimi/përshkrimi plotësohen nga njëri-tjetri kur mungojnë"
        )
    return dict(mapping)


def preview_prices(
    data: bytes,
    filename: str,
    sheet: str | None = None,
    mapping: dict | None = None,
    header_row: int | None = None,
    currency: str = "ALL",
    code_prefix: str = "IMPORT",
) -> dict:
    if currency not in {"ALL", "EUR"}:
        raise ValueError("Zgjidhni monedhën e importit ALL ose EUR")
    if not isinstance(code_prefix, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,40}", code_prefix
    ):
        raise ValueError(
            "Prefiksi i kodeve duhet të ketë 1–40 shkronja, numra, vizë ose nënvizë"
        )
    workbook = _open_catalog(data, filename)
    try:
        if not workbook.sheets:
            raise ValueError("Skedari nuk përmban fletë pune")
        selected = (
            next((entry for entry in workbook.sheets if entry.name == sheet), None)
            if sheet is not None
            else workbook.sheets[0]
        )
        if selected is None:
            raise ValueError("Fleta e zgjedhur nuk u gjet")
        info = _sheet_info(selected)
        automatic = mapping is None
        if (
            automatic
            and header_row is not None
            and isinstance(header_row, int)
            and not isinstance(header_row, bool)
            and 0 <= header_row < selected.row_count
        ):
            for index, cells in enumerate(selected.rows()):
                if index == header_row:
                    detected, repeated = _suggest(cells)
                    info["suggested_mapping"] = detected
                    info["ambiguous_headers"] = repeated
                    info["warnings"] = (
                        [
                            "Kolona të paqarta: zgjidhni hartëzim manual për fushat e përsëritura."
                        ]
                        if repeated
                        else []
                    )
                    break
        mapping = _validate_mapping(
            info["suggested_mapping"] if automatic else mapping, selected.column_count
        )
        header_row = info["header_row"] if header_row is None else header_row
        if (
            not isinstance(header_row, int)
            or isinstance(header_row, bool)
            or header_row < 0
            or header_row >= max(selected.row_count, 1)
        ):
            raise ValueError(
                "Rreshti i titujve duhet të jetë indeks zero i një rreshti ekzistues"
            )
        warnings = list(info["warnings"]) if automatic else []
        ambiguous = info["ambiguous_headers"] if automatic else {}
        missing = [field for field in ("unit", "price") if field not in mapping]
        if not ({"name", "description"} & set(mapping)):
            missing.append("name")
        rows, seen_codes = [], set()
        data_rows = 0
        counts = {"valid": 0, "invalid": 0, "skipped": 0}
        for index, cells in enumerate(selected.rows()):
            if index <= header_row:
                continue
            source_row = index + 1
            if any(not _blank(value) for value in cells):
                data_rows += 1
                if data_rows > MAX_IMPORT_ROWS:
                    raise ValueError(
                        "Importi lejon maksimumi 10000 rreshta me të dhëna pas titujve; ndani skedarin në pjesë"
                    )
            entry = {
                "source_row": source_row,
                "status": "invalid",
                "values": {},
                "errors": [],
                "warnings": [],
                "numeric_review_required": False,
            }
            rows.append(entry)
            raw = {
                field: cells[col] if col < len(cells) else None
                for field, col in mapping.items()
            }
            if not any(not _blank(value) for value in cells):
                entry.update(status="skipped", warnings=["Rresht bosh"])
            else:
                display = (
                    raw.get("name")
                    if not _blank(raw.get("name"))
                    else raw.get("description")
                )
                if (
                    _SUBTOTAL.match(normalize_header(display))
                    and _blank(raw.get("code"))
                    and (
                        _blank(raw.get("unit"))
                        or normalize_header(raw.get("unit"))
                        in {"all", "eur", "lek", "leke"}
                    )
                ):
                    entry.update(
                        status="skipped",
                        warnings=[
                            "Nëntotal ose rresht përmbledhës; nuk importohet si çmim"
                        ],
                    )
                elif (
                    not missing
                    and not ambiguous
                    and not _blank(display)
                    and _blank(raw.get("unit"))
                    and _blank(raw.get("price"))
                    and _blank(raw.get("code"))
                ):
                    entry.update(
                        status="skipped",
                        warnings=[
                            "Titull pa njësi dhe çmim; kontrolloni nëse duhej të ishte artikull"
                        ],
                    )
                elif len(_suggest(cells)[0]) >= 3 and {"unit", "price"}.issubset(
                    _suggest(cells)[0]
                ):
                    entry.update(
                        status="skipped", warnings=["Rresht titujsh i përsëritur"]
                    )
                else:
                    for field in missing:
                        entry["errors"].append(
                            {
                                "field": field,
                                "message": "Kolona e detyrueshme nuk është hartuar",
                            }
                        )
                    for field in ambiguous:
                        entry["errors"].append(
                            {
                                "field": field,
                                "message": "Kolona të përsëritura; zgjidhni hartëzim manual",
                            }
                        )
                    values = {}
                    for field, value in raw.items():
                        if _blank(value):
                            continue
                        try:
                            if field in _NUMERIC_FIELDS:
                                values[field] = _number(
                                    value, places=4 if field == "vat_rate" else 6
                                )
                                if isinstance(value, str) and re.fullmatch(
                                    r"[+]?[1-9]\d{0,2}[.,]\d{3}", value.strip()
                                ):
                                    entry["numeric_review_required"] = True
                                    entry["warnings"].append(
                                        f"{field}: ndarësi me tri shifra u lexua si ndarës dhjetor; mund të jetë ndarës mijëshe — verifikoni vlerën para ruajtjes"
                                    )
                            elif field in _BOOLEAN_FIELDS:
                                values[field] = _boolean(value)
                            elif field in _DATE_FIELDS:
                                text = (
                                    value.date().isoformat()
                                    if isinstance(value, datetime)
                                    else value.isoformat()
                                    if isinstance(value, date)
                                    else _text(value)
                                )
                                values[field] = date.fromisoformat(text).isoformat()
                            else:
                                values[field] = _text(value)
                        except (ValueError, TypeError) as exc:
                            entry["errors"].append(
                                {
                                    "field": field,
                                    "message": "Data duhet të jetë YYYY-MM-DD"
                                    if field in _DATE_FIELDS
                                    else str(exc)
                                    if field in _NUMERIC_FIELDS
                                    or field in _BOOLEAN_FIELDS
                                    else "Vlerë e pavlefshme",
                                }
                            )
                    if not values.get("name") and values.get("description"):
                        values["name"] = values["description"][:300]
                        entry["warnings"].append("Emërtimi u mor nga përshkrimi")
                        if len(values["description"]) > 300:
                            entry["warnings"].append(
                                "Emërtimi i shfaqjes u shkurtua në 300 karaktere; përshkrimi i plotë u ruajt"
                            )
                    if not values.get("description") and values.get("name"):
                        values["description"] = values["name"]
                        entry["warnings"].append("Përshkrimi u mor nga emërtimi")
                        if len(values["name"]) > 300:
                            values["name"] = values["name"][:300]
                            entry["warnings"].append(
                                "Emërtimi i shfaqjes u shkurtua në 300 karaktere; përshkrimi i plotë u ruajt"
                            )
                    if not values.get("code"):
                        values["code"] = f"{code_prefix.upper()}-{source_row:06d}"
                        entry["warnings"].append(
                            "Kodi mungonte: u gjenerua kod nga prefiksi dhe numri origjinal i rreshtit; kontrollojeni para ruajtjes"
                        )
                    values.setdefault("currency", currency)
                    values.setdefault("reason", "Import nga Excel")
                    for field in ("unit", "price"):
                        if field not in values and not any(
                            error["field"] == field for error in entry["errors"]
                        ):
                            entry["errors"].append(
                                {
                                    "field": field,
                                    "message": "Vlera është e detyrueshme; nuk vendoset automatikisht",
                                }
                            )
                    try:
                        validated = PriceInput.model_validate(values)
                    except ValidationError as exc:
                        for issue in exc.errors(
                            include_input=False, include_context=False
                        ):
                            field = str(issue["loc"][0])
                            if not any(
                                error["field"] == field for error in entry["errors"]
                            ):
                                entry["errors"].append(
                                    {
                                        "field": field,
                                        "message": "Vlerë e munguar, e pavlefshme ose jashtë kufijve të lejuar",
                                    }
                                )
                    else:
                        if validated.code in seen_codes:
                            entry["errors"].append(
                                {
                                    "field": "code",
                                    "message": "Kod i përsëritur brenda skedarit; ndryshoni ose përjashtoni rreshtin",
                                }
                            )
                        elif not entry["errors"]:
                            seen_codes.add(validated.code)
                            entry.update(
                                status="valid", values=validated.model_dump(mode="json")
                            )
            counts[entry["status"]] += 1
        return {
            "rows": rows,
            "valid_count": counts["valid"],
            "error_count": counts["invalid"],
            "skipped_count": counts["skipped"],
            "sheet": selected.name,
            "mapping": mapping,
            "header_row": header_row,
            "warnings": warnings,
        }
    except (ParseError, DefusedXmlException, BadZipFile, EOFError) as exc:
        raise ValueError("Përmbajtja Excel është e dëmtuar ose e pasigurt") from exc
    finally:
        workbook.close()
