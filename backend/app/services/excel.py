"""Bounded, macro-free Excel import/export with explicit column mapping.

Mappings use zero-based column indices and header_row is zero-based; source_row
always denotes the original one-based Excel row. Workbooks are never executed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import re
import unicodedata
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 3000
MAX_ROWS = 50000
MAX_COLUMNS = 200
MAX_CELLS = 1_000_000
PREVIEW_ROWS = 30

_FIELDS = {
    "item_number": [
        "nr",
        "nr rendor",
        "no",
        "item",
        "item number",
        "numri",
        "pozicioni",
        "poz",
    ],
    "code": ["kodi", "kod", "code", "item code", "kodi analizes", "analiza"],
    "description": [
        "pershkrimi",
        "pershkrim",
        "emertimi",
        "emertim",
        "description",
        "work description",
        "punimet",
        "pershkrimi i punimeve",
        "pershkrimi i punimit",
        "emertimi i punimeve",
        "pershkrimi dhe specifikimet",
    ],
    "unit": ["njesia", "njesi", "unit", "uom", "nj matese", "njesia matese"],
    "quantity": ["sasia", "sasi", "quantity", "qty", "volume"],
    "existing_unit_price": [
        "cmimi",
        "cmim",
        "cmimi njesi",
        "cmimi per njesi",
        "cmimi i njesise",
        "unit price",
        "price",
        "rate",
    ],
    "existing_total": ["vlera", "vlere", "total", "amount", "shuma", "vlera totale"],
}
_SUBTOTAL = re.compile(
    r"^(?:nen\s*total|subtotal|sub total|totali?|gjithsej|permbledhje|summary)(?:\b|:)",
    re.I,
)


def _normalize(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def _safe_text(value):
    """Prevent Excel formula injection while retaining the visible original text."""
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _decimal(value, label: str) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label}: vlerë numerike e pavlefshme")
    raw = str(value).strip().replace("\u00a0", "").replace(" ", "")
    # Both common export conventions are supported; no thousands separator is
    # inferred from one comma, so 1,234 means decimal 1.234 rather than 1234.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: vlerë numerike e pavlefshme") from exc
    if not number.is_finite() or abs(number) > Decimal("1e15"):
        raise ValueError(f"{label}: vlerë numerike jashtë kufijve")
    return number


def _open(data: bytes, *, read_only=True, data_only=True):
    if not isinstance(data, bytes) or not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Skedari Excel është bosh ose tejkalon kufirin 20 MB")
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError("Shumë hyrje në arkivin Excel")
            if sum(i.file_size for i in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Përmbajtja e çkompresuar e Excel tejkalon kufirin")
            for entry in entries:
                if entry.flag_bits & 1:
                    raise ValueError("Excel i enkriptuar nuk mbështetet")
                path = entry.filename.replace("\\", "/")
                if path.startswith("/") or ".." in path.split("/"):
                    raise ValueError("Rrugë e pasigurt në arkivin Excel")
                if (
                    entry.file_size > 1024 * 1024
                    and entry.file_size > max(entry.compress_size, 1) * 1000
                ):
                    raise ValueError("Raport i pasigurt kompresimi në Excel")
            if "xl/workbook.xml" not in archive.namelist():
                raise ValueError("Kërkohet skedar .xlsx ose .xlsm; .xls nuk mbështetet")
        workbook = load_workbook(
            BytesIO(data),
            read_only=read_only,
            data_only=data_only,
            keep_links=False,
            keep_vba=False,
        )
        if len(workbook.worksheets) > 100:
            workbook.close()
            raise ValueError("Shumë fletë në Excel")
        for sheet in workbook.worksheets:
            if (
                sheet.max_row is None
                or sheet.max_column is None
                or sheet.max_row > MAX_ROWS
                or sheet.max_column > MAX_COLUMNS
            ):
                workbook.close()
                raise ValueError("Excel tejkalon kufirin e rreshtave ose kolonave")
        if (
            sum(sheet.max_row * sheet.max_column for sheet in workbook.worksheets)
            > MAX_CELLS
        ):
            workbook.close()
            raise ValueError("Excel tejkalon kufirin total të qelizave")
        return workbook
    except (BadZipFile, InvalidFileException, KeyError, OSError, ParseError) as exc:
        raise ValueError("Skedar Excel i pavlefshëm ose i dëmtuar") from exc


def _suggest(values: list) -> dict:
    result = {}
    for col, value in enumerate(values):
        normalized = _normalize(value)
        if not normalized:
            continue
        for field, aliases in _FIELDS.items():
            if field not in result and normalized in aliases:
                result[field] = col
                break
    return result


def inspect_workbook(data: bytes) -> dict:
    workbook = _open(data)
    try:
        sheets = []
        for sheet in workbook.worksheets:
            preview = [
                list(row)
                for row in sheet.iter_rows(
                    min_row=1,
                    max_row=min(PREVIEW_ROWS, sheet.max_row),
                    values_only=True,
                )
            ]
            candidates = [(index, _suggest(row)) for index, row in enumerate(preview)]
            header_row, mapping = max(
                candidates,
                key=lambda pair: len(pair[1]) + (2 if "description" in pair[1] else 0),
                default=(0, {}),
            )
            # Dates and Decimal values in previews must be JSON serializable.
            preview = [
                [v.isoformat() if hasattr(v, "isoformat") else v for v in row]
                for row in preview
            ]
            sheets.append(
                {
                    "name": sheet.title,
                    "preview": preview,
                    "header_row": header_row,
                    "suggested_mapping": mapping,
                    "row_count": sheet.max_row,
                    "column_count": sheet.max_column,
                }
            )
        return {"sheets": sheets}
    finally:
        workbook.close()


def import_rows(data: bytes, sheet: str, mapping: dict, header_row: int = 0) -> dict:
    if not isinstance(header_row, int) or header_row < 0 or header_row >= MAX_ROWS:
        raise ValueError("Rreshti i titullit është i pavlefshëm")
    if not isinstance(mapping, dict) or not {
        "description",
        "unit",
        "quantity",
    }.issubset(mapping):
        raise ValueError("Hartoni kolonat: përshkrim, njësi dhe sasi")
    if any(
        field not in _FIELDS
        or not isinstance(col, int)
        or isinstance(col, bool)
        or col < 0
        or col >= MAX_COLUMNS
        for field, col in mapping.items()
    ):
        raise ValueError("Hartëzim kolonash i pavlefshëm")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Çdo fushë duhet të ketë kolonë të veçantë")
    workbook = _open(data)
    try:
        if sheet not in workbook.sheetnames:
            raise ValueError("Fleta nuk u gjet")
        worksheet = workbook[sheet]
        if max(mapping.values()) >= worksheet.max_column:
            raise ValueError("Kolona e hartuar nuk ekziston")
        rows, rejected = [], []
        for source_row, cells in enumerate(
            worksheet.iter_rows(min_row=header_row + 2, values_only=True),
            start=header_row + 2,
        ):
            values = {
                key: cells[column] if column < len(cells) else None
                for key, column in mapping.items()
            }
            if all(
                value is None or str(value).strip() == "" for value in values.values()
            ):
                rejected.append({"source_row": source_row, "reason": "empty"})
                continue
            description = str(values.get("description") or "")
            if _SUBTOTAL.match(_normalize(description)):
                rejected.append({"source_row": source_row, "reason": "subtotal"})
                continue
            if not description.strip():
                rejected.append(
                    {"source_row": source_row, "reason": "missing_description"}
                )
                continue
            try:
                quantity = _decimal(values.get("quantity"), "Sasia")
                if quantity is None:
                    rejected.append(
                        {
                            "source_row": source_row,
                            "reason": "heading_or_missing_quantity",
                        }
                    )
                    continue
                if quantity <= 0:
                    raise ValueError("Sasia duhet të jetë pozitive")
                if not str(values.get("unit") or "").strip():
                    raise ValueError("Njësia mungon")
                price = _decimal(values.get("existing_unit_price"), "Çmimi")
                total = _decimal(values.get("existing_total"), "Vlera")
                if (price is not None and price < 0) or (
                    total is not None and total < 0
                ):
                    raise ValueError("Çmimi ose vlera nuk mund të jetë negative")
            except ValueError as exc:
                rejected.append({"source_row": source_row, "reason": str(exc)})
                continue
            item_number = values.get("item_number")
            rows.append(
                {
                    "item_number": str(item_number) if item_number is not None else "",
                    "code": str(values.get("code") or ""),
                    "description": description,
                    "unit": str(values["unit"]).strip(),
                    "quantity": quantity,
                    "existing_unit_price": price,
                    "existing_total": total,
                    "source_row": source_row,
                }
            )
        return {
            "rows": rows,
            "rejected": rejected,
            "sheet": sheet,
            "mapping": mapping,
            "header_row": header_row,
        }
    finally:
        workbook.close()


def _output(workbook) -> bytes:
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _warning(row: dict) -> str:
    warnings = (
        row.get("matching_warnings")
        or row.get("warnings")
        or row.get("discrepancies")
        or []
    )
    if isinstance(warnings, list):
        warnings = "; ".join(str(value) for value in warnings)
    if (row.get("match_result") or {}).get("classification") == "no_match":
        warnings = "; ".join(filter(None, [str(warnings), "No match found"]))
    note = str(row.get("notes") or "")
    if row.get("unit_price") is None:
        warnings = "; ".join(filter(None, [str(warnings), "Pa çmim / i pazgjidhur"]))
    return "; ".join(filter(None, [note, str(warnings)]))


def _number(value):
    return _decimal(value, "Vlera") if value is not None and value != "" else None


def _summary(workbook, project: dict, totals: dict, title="Përmbledhje"):
    sheet = workbook.create_sheet(title)
    sheet.append(["SmartEstimate AI", "Preventiv"])
    for key, label in [
        ("name", "Projekti"),
        ("client", "Klienti"),
        ("location", "Vendndodhja"),
        ("currency", "Monedha"),
    ]:
        sheet.append([label, _safe_text(str(project.get(key) or ""))])
    sheet.append([])
    labels = {
        "subtotal": "Nëntotali",
        "direct_cost": "Kosto direkte",
        "overhead": "Shpenzime të përgjithshme",
        "profit": "Fitimi",
        "discount": "Zbritja",
        "vat": "TVSH",
        "grand_total": "Totali përfundimtar",
        "other_charges": "Tarifa të tjera",
    }
    for key, value in totals.items():
        if isinstance(value, (str, int, Decimal, float)):
            try:
                number = _number(value)
            except ValueError:
                number = _safe_text(str(value))
            sheet.append([labels.get(key, key), number])
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 40
    for row in sheet.iter_rows():
        row[0].font = Font(bold=True)
        if len(row) > 1 and isinstance(row[1].value, (Decimal, int, float)):
            row[1].number_format = "#,##0.00"


def export_standard(project: dict, rows: list[dict], totals: dict) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Preventivi"
    sheet.append(
        [
            "Nr.",
            "Përshkrimi origjinal i punimeve",
            "Njësia",
            "Sasia",
            "Çmimi njësi",
            "Vlera",
            "Shënime / paralajmërime",
            "Approval status",
            "Matching confidence",
        ]
    )
    for row in rows:
        quantity, price = _number(row.get("quantity")), _number(row.get("unit_price"))
        total = _number(row.get("total"))
        if total is None and quantity is not None and price is not None:
            total = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sheet.append(
            [
                _safe_text(str(row.get("item_number") or "")),
                _safe_text(str(row.get("description") or "")),
                _safe_text(str(row.get("unit") or "")),
                quantity,
                price,
                total,
                _safe_text(_warning(row)),
                row.get("decision", "pending"),
                (row.get("match_result") or {}).get("confidence"),
            ]
        )
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in {
        "A": 12,
        "B": 70,
        "C": 12,
        "D": 18,
        "E": 20,
        "F": 22,
        "G": 65,
        "H": 20,
        "I": 22,
    }.items():
        sheet.column_dimensions[column].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="183249")
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        row[8].number_format = "0.00%"
        for cell in row[3:6]:
            cell.number_format = "#,##0.00"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.print_title_rows = "1:1"
    _summary(workbook, project, totals)
    return _output(workbook)


_SAFE_FORMULA_FUNCTIONS = {
    "SUM",
    "SUBTOTAL",
    "ROUND",
    "ROUNDUP",
    "ROUNDDOWN",
    "IF",
    "IFERROR",
    "MIN",
    "MAX",
    "ABS",
    "COUNT",
    "COUNTA",
    "COUNTIF",
    "COUNTIFS",
    "SUMIF",
    "SUMIFS",
    "AND",
    "OR",
    "NOT",
    "AVERAGE",
    "ISNUMBER",
    "ISBLANK",
}


def _safe_formula(formula: str) -> bool:
    if any(
        token in formula for token in ("[", "]", "|", "http:", "https:", "file:", "\\")
    ):
        return False
    functions = re.findall(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(", formula)
    return all(function.upper() in _SAFE_FORMULA_FUNCTIONS for function in functions)


def export_original(
    data: bytes,
    sheet: str,
    rows: list[dict],
    mapping: dict,
    header_row: int = 0,
    *,
    project: dict | None = None,
    totals: dict | None = None,
) -> bytes:
    workbook = _open(data, read_only=False, data_only=False)
    try:
        if sheet not in workbook.sheetnames:
            raise ValueError("Fleta nuk u gjet")
        worksheet = workbook[sheet]
        if header_row < 0 or header_row >= MAX_ROWS:
            raise ValueError("Rreshti i titullit është i pavlefshëm")
        # Preserve existing styles and formulas; neutralize dangerous formulas
        # sourced from input text only when writing new user-provided cells.
        columns = {}
        next_column = worksheet.max_column + 1
        for field, source_key, label in [
            ("unit_price", "existing_unit_price", "Çmimi njësi"),
            ("total", "existing_total", "Vlera"),
            ("warnings", "", "Shënime / paralajmërime"),
            ("decision", "", "Approval status"),
            ("confidence", "", "Matching confidence"),
        ]:
            mapped = mapping.get(source_key) if source_key else None
            if mapped is not None and (
                not isinstance(mapped, int) or mapped < 0 or mapped >= MAX_COLUMNS
            ):
                raise ValueError("Hartëzim kolonash i pavlefshëm")
            columns[field] = mapped + 1 if mapped is not None else next_column
            if mapped is None:
                next_column += 1
            worksheet.cell(header_row + 1, columns[field], label)
            worksheet.column_dimensions[get_column_letter(columns[field])].width = (
                24 if field != "warnings" else 55
            )
        for row in rows:
            source_row = row.get("source_row")
            if (
                not isinstance(source_row, int)
                or source_row <= header_row + 1
                or source_row > MAX_ROWS
            ):
                raise ValueError("Rreshti origjinal mungon ose është i pavlefshëm")
            quantity, price = (
                _number(row.get("quantity")),
                _number(row.get("unit_price")),
            )
            total = _number(row.get("total"))
            if total is None and quantity is not None and price is not None:
                total = (quantity * price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            worksheet.cell(source_row, columns["unit_price"]).value = price
            worksheet.cell(source_row, columns["total"]).value = total
            worksheet.cell(source_row, columns["warnings"], _safe_text(_warning(row)))
            worksheet.cell(source_row, columns["decision"], row.get("decision", "pending"))
            worksheet.cell(source_row, columns["confidence"]).value = (
                row.get("match_result") or {}
            ).get("confidence")
            worksheet.cell(source_row, columns["confidence"]).number_format = "0.00%"
            for field in ("unit_price", "total"):
                worksheet.cell(source_row, columns[field]).number_format = "#,##0.00"
        # External workbook links and VBA were removed on load. Remove hyperlinks
        # so opening an exported original never activates an imported URL.
        for worksheet_item in workbook.worksheets:
            for cells in worksheet_item.iter_rows():
                for cell in cells:
                    if cell.hyperlink:
                        cell.hyperlink = None
                    if cell.data_type == "f" and not _safe_formula(str(cell.value)):
                        cell.value = _safe_text(str(cell.value))
        for name in list(workbook.defined_names):
            if not _safe_formula(workbook.defined_names[name].attr_text or ""):
                del workbook.defined_names[name]
        summary_name = "SmartEstimate"
        while summary_name in workbook.sheetnames:
            summary_name += "_"
        summary = workbook.create_sheet(summary_name)
        summary.append(["SmartEstimate AI", "Eksport i shabllonit origjinal"])
        summary.append(["Rreshta të vlerësuar", len(rows)])
        summary.append(
            ["Rreshta pa çmim", sum(row.get("unit_price") is None for row in rows)]
        )
        summary.append(
            [
                "Shënim",
                "Makrot, lidhjet e jashtme dhe formulat e pasigurta janë hequr; kontrolloni totalet e shabllonit.",
            ]
        )
        summary.column_dimensions["A"].width = 30
        summary.column_dimensions["B"].width = 110
        if project is not None and totals is not None:
            financial_title = "Përmbledhje financiare"
            while financial_title in workbook.sheetnames:
                financial_title += "_"
            _summary(workbook, project, totals, title=financial_title)
        return _output(workbook)
    except Exception:
        workbook.close()
        raise
