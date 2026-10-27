"""Independent regressions for supplier-price parsing and round-trip integrity."""

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.schemas import PriceInput
from app.services.price_import import _number, preview_prices


def price_workbook(headers, rows):
    book = Workbook()
    sheet = book.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


@pytest.mark.parametrize("value", ["1 23 4", "12 34", "1\u00a023\u00a04", "1\t2"])
def test_malformed_space_grouping_never_changes_a_price(value):
    with pytest.raises(ValueError):
        _number(value)


@pytest.mark.parametrize("value", ["1,000", "1.000"])
def test_ambiguous_string_separator_is_visible_to_reviewer(value):
    data = price_workbook(
        ["code", "name", "description", "unit", "price"],
        [["A", "Beton", "Beton", "m³", value]],
    )
    result = preview_prices(data, "supplier.xlsx")
    row = result["rows"][0]
    assert row["status"] == "valid"
    assert Decimal(row["values"]["price"]) == Decimal("1")
    warnings = " ".join(row["warnings"]).lower()
    assert "ndar" in warnings or "paqart" in warnings or "mij" in warnings


def test_numeric_excel_decimal_does_not_receive_string_separator_warning():
    data = price_workbook(
        ["code", "name", "description", "unit", "price"],
        [["A", "Beton", "Beton", "m³", 1.234]],
    )
    row = preview_prices(data, "supplier.xlsx")["rows"][0]
    assert row["status"] == "valid"
    assert row["warnings"] == []


def test_total_station_is_an_item_not_a_subtotal_heading():
    data = price_workbook(
        ["code", "name", "unit", "price"],
        [["TS07", "Total station Leica TS07", "copë", 1200]],
    )
    result = preview_prices(data, "supplier.xlsx")
    assert result["valid_count"] == 1
    assert result["skipped_count"] == 0
    assert result["rows"][0]["values"]["code"] == "TS07"


def test_all_optional_export_fields_survive_preview_roundtrip(client, user):
    source = PriceInput(
        code="FV-X",
        name="Montim strukture FV",
        description="Strukturë për module FV",
        synonyms="strukturë, mbajtëse",
        technical_specs="Alumin 6063",
        category="FV",
        subcategory="Struktura",
        unit="m²",
        price="1234.567891",
        currency="EUR",
        price_kind="installed",
        supply_included=True,
        installation_included=True,
        supplier="Furnitor Çelik",
        price_date="2026-01-20",
        valid_until="2027-01-20",
        vat_included=True,
        vat_rate="19.25",
        material_cost="100.125",
        labor_cost="200.25",
        machinery_cost="10.5",
        transport_cost="15.75",
        other_cost="12.125",
        notes="Sasi të përcaktuara nga inxhinieri.",
        active=False,
    )
    response = client.post("/api/prices", json=source.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    exported = client.get("/api/prices/export")
    assert exported.status_code == 200, exported.text
    rows = preview_prices(exported.content, "prices.xlsx")["rows"]
    assert len(rows) == 1
    assert rows[0]["status"] == "valid", rows[0]
    expected = source.model_dump(mode="json")
    expected["reason"] = "Import nga Excel"
    actual = rows[0]["values"]
    numeric = {
        "price",
        "vat_rate",
        "material_cost",
        "labor_cost",
        "machinery_cost",
        "transport_cost",
        "other_cost",
    }
    for key, value in expected.items():
        assert (
            (Decimal(actual[key]) == Decimal(value))
            if key in numeric
            else actual[key] == value
        ), key
