from decimal import Decimal

import pytest

from app.services.calculations import (
    calculate_estimate,
    composite_cost,
    convert_money,
    snapshot_price,
)


def approved(**overrides):
    return {
        "id": 1,
        "decision": "approved",
        "quantity": "3",
        "unit_price": "0.335",
        **overrides,
    }


def test_lines_round_before_aggregation():
    result = calculate_estimate({"vat_rate": 0}, [approved(), approved(id=2)])
    assert result["subtotal"] == "2.02"
    assert result["grand_total"] == "2.02"
    assert result["incomplete"] is False


def test_financial_order_direct_and_sequential_bases():
    project = {
        "vat_rate": 20,
        "overhead_percent": 10,
        "profit_percent": 20,
        "discount_percent": 10,
        "other_charges": "5",
    }
    row = approved(quantity=1, unit_price=100)
    result = calculate_estimate(project, [row])
    assert result["overhead"] == "10.00"
    assert result["profit"] == "20.00"
    assert result["discount"] == "13.00"
    assert result["taxable_amount"] == "122.00"
    assert result["vat"] == "24.40"
    assert result["grand_total"] == "146.40"
    sequential = calculate_estimate({**project, "calculation_base": "subtotal"}, [row])
    assert sequential["profit"] == "22.00"
    assert sequential["grand_total"] == "148.56"


def test_pending_rejected_and_missing_prices_are_explicit():
    result = calculate_estimate(
        {"vat_rate": 0},
        [
            approved(unit_price=None),
            approved(id=2, decision="pending"),
            approved(id=3, decision="rejected"),
            approved(id=4, currency="EUR"),
        ],
    )
    assert result["incomplete"]
    assert result["unresolved_count"] == 4
    assert result["subtotal"] == "0.00"
    assert [r["reason"] for r in result["unresolved_rows"]] == [
        "missing_price",
        "unapproved",
        "unapproved",
        "currency_mismatch",
    ]
    assert all(r["total"] is None for r in result["line_totals"])


def test_zero_price_is_allowed_only_when_explicit_and_approved():
    assert calculate_estimate({}, [approved(unit_price="0")])["incomplete"] is False
    assert calculate_estimate({}, [approved(quantity="-1")])["incomplete"] is True


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", True, None])
def test_invalid_amounts_rejected(value):
    with pytest.raises(ValueError):
        convert_money(value, "ALL", "ALL", {})


def test_currency_conversion_requires_explicit_direction():
    assert convert_money("2.50", "EUR", "ALL", {"EUR:ALL": "100.25"}) == Decimal(
        "250.6250"
    )
    assert convert_money("2.50", "EUR", "EUR", {}) == Decimal("2.50")
    with pytest.raises(ValueError, match="Mungon"):
        convert_money(10, "ALL", "EUR", {"EUR:ALL": 100})
    with pytest.raises(ValueError):
        convert_money(10, "EUR", "ALL", {"EUR:ALL": 0})


def test_snapshot_converts_units_currency_and_removes_vat():
    item = {
        "id": 4,
        "price": "120",
        "unit": "kW",
        "currency": "EUR",
        "vat_included": True,
        "vat_rate": "20",
        "material_cost": "99",
    }
    result = snapshot_price(item, "W", "ALL", {"EUR:ALL": 100})
    assert Decimal(result["unit_price"]) == Decimal("10")
    assert result["original_price"] == "120"
    assert result["component_costs_informational_only"]
    item["price"] = "240"
    assert Decimal(result["unit_price"]) == Decimal("10")


def test_snapshot_rejects_incompatible_units_and_missing_prices():
    with pytest.raises(ValueError, match="papajtueshme"):
        snapshot_price({"price": 5, "unit": "m2", "currency": "ALL"}, "m3", "ALL", {})
    with pytest.raises(ValueError):
        snapshot_price({"price": None, "unit": "m", "currency": "ALL"}, "m", "ALL", {})


def test_components_are_not_added_twice():
    row = approved(quantity=1, unit_price=100, material_cost=100, labor_cost=50)
    assert calculate_estimate({"vat_rate": 0}, [row])["grand_total"] == "100.00"


def test_resource_costs_and_waste():
    assert composite_cost(
        [
            {"coefficient": "2", "unit_cost": "5.25", "waste_percent": "10"},
            {"coefficient": "0.5", "unit_cost": "20", "waste_percent": 0},
        ]
    ) == Decimal("21.550")
    for resources in [
        [],
        [{"coefficient": 0, "unit_cost": 1}],
        [{"coefficient": 1, "unit_cost": -1}],
        [{"coefficient": 1, "unit_cost": 1, "waste_percent": 101}],
    ]:
        with pytest.raises(ValueError):
            composite_cost(resources)


@pytest.mark.parametrize(
    "field", ["vat_rate", "profit_percent", "overhead_percent", "discount_percent"]
)
def test_invalid_percentages(field):
    with pytest.raises(ValueError):
        calculate_estimate({field: 101}, [])


def test_large_valid_lines_keep_precision_in_aggregate_totals():
    rows = [
        approved(id=index, quantity="1000000000000", unit_price="1000000000000")
        for index in range(1000)
    ]
    result = calculate_estimate(
        {"vat_rate": "20", "overhead_percent": "10", "profit_percent": "5"}, rows
    )
    assert result["subtotal"] == "1000000000000000000000000000.00"
    assert result["grand_total"] == "1380000000000000000000000000.00"
    assert result["approved_count"] == 1000
