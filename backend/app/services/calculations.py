"""Deterministic monetary calculations; all public amounts are decimal strings.

Prices are authoritative. Resource/component amounts describe their derivation and
are never added to that price again. Each line is rounded before aggregate totals.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any

from .units import conversion_factor

CENT = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


def decimal_value(
    value: Any, field: str = "amount", *, nonnegative: bool = True
) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field}: kërkohet një numër i vlefshëm")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field}: kërkohet një numër i vlefshëm") from None
    if not result.is_finite() or (nonnegative and result < ZERO):
        raise ValueError(f"{field}: kërkohet një numër i fundëm jo negativ")
    # Keeps accepted values within the schema's financial precision.
    if abs(result) >= Decimal("100000000000000"):
        raise ValueError(f"{field}: vlera tejkalon kufirin e lejuar")
    return result


def money(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        return value.quantize(CENT, rounding=ROUND_HALF_UP)


def amount_text(value: Decimal) -> str:
    return format(money(value), ".2f")


def percent(value: Any, field: str) -> Decimal:
    result = decimal_value(value, field)
    if result > HUNDRED:
        raise ValueError(f"{field}: përqindja duhet të jetë nga 0 deri 100")
    return result


def convert_money(amount: Any, source: str, target: str, rates: dict) -> Decimal:
    """Apply a directional, explicitly configured rate; never infer market rates."""
    value = decimal_value(amount)
    if source not in {"ALL", "EUR"} or target not in {"ALL", "EUR"}:
        raise ValueError("Monedha e pambështetur; përdorni ALL ose EUR")
    if source == target:
        return value
    key = f"{source}:{target}"
    if key not in rates:
        raise ValueError(f"Mungon kursi i këmbimit {key}")
    rate = decimal_value(rates[key], "exchange_rate")
    if rate <= ZERO:
        raise ValueError("Kursi i këmbimit duhet të jetë më i madh se zero")
    with localcontext() as ctx:
        ctx.prec = 40
        return value * rate


def snapshot_price(
    item: dict,
    row_unit: str,
    project_currency: str,
    rates: dict,
    custom_rules: Any = None,
) -> dict:
    """Freeze database price and conversion inputs without monetary rounding.

    Existing BOQ unit prices are not implicitly used. VAT-inclusive database
    prices are first reduced to net amounts so project VAT applies only once.
    Validity warnings require review by the caller rather than guessing a price.
    """
    if item.get("active") is False:
        raise ValueError("Artikulli i çmimit është i arkivuar")
    price = decimal_value(item.get("price"), "price")
    factor = conversion_factor(row_unit, item.get("unit", ""), custom_rules)
    if factor is None:
        raise ValueError(
            f"Njësi të papajtueshme: {row_unit} dhe {item.get('unit', '')}"
        )
    factor = decimal_value(factor, "unit_factor")
    if factor == ZERO:
        raise ValueError("Faktori i njësisë duhet të jetë pozitiv")
    source_currency = item.get("currency", "")
    vat_rate = percent(item.get("vat_rate", 0), "vat_rate")
    net = price
    with localcontext() as ctx:
        ctx.prec = 40
        if item.get("vat_included", False):
            net = price / (Decimal(1) + vat_rate / HUNDRED)
        converted = convert_money(net, source_currency, project_currency, rates)
        effective = converted * factor
    warnings = []
    valid_until = item.get("valid_until")
    if valid_until:
        try:
            if date.fromisoformat(str(valid_until)) < date.today():
                warnings.append(
                    "Çmimi ka kaluar datën e vlefshmërisë; kërkohet shqyrtim."
                )
        except ValueError:
            warnings.append("Data e vlefshmërisë së çmimit është e pavlefshme.")
    return {
        "item_id": item.get("id"),
        "version": item.get("version", 1),
        "code": item.get("code", ""),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "technical_specs": item.get("technical_specs", ""),
        "price_kind": item.get("price_kind", "direct"),
        "supply_included": bool(item.get("supply_included", False)),
        "installation_included": bool(item.get("installation_included", False)),
        "original_price": str(price),
        "original_currency": source_currency,
        "original_unit": item.get("unit", ""),
        "unit": row_unit,
        "currency": project_currency,
        "unit_factor": str(factor),
        "exchange_rate": "1"
        if source_currency == project_currency
        else str(rates[f"{source_currency}:{project_currency}"]),
        "vat_included": bool(item.get("vat_included", False)),
        "vat_rate": str(vat_rate),
        "net_database_price": str(net),
        "unit_price": str(effective),
        "warnings": warnings,
        "component_costs_informational_only": True,
    }


def calculate_estimate(project: dict, rows: list[dict]) -> dict:
    # Aggregate precision must exceed per-column SQL precision: thousands of
    # individually valid large lines can have a substantially larger sum.
    with localcontext() as ctx:
        ctx.prec = 50
        return _calculate_estimate(project, rows)


def _calculate_estimate(project: dict, rows: list[dict]) -> dict:
    """Calculate approved lines, explicitly expose every unresolved line.

    Order: rounded lines -> overhead -> profit -> discount -> other charges ->
    VAT. With direct base, both markups use subtotal. With subtotal base, profit
    uses subtotal plus overhead. Percentages are additive markups, not gross
    margin percentages; this distinction is returned in calculation_details.
    """
    currency = project.get("currency", "ALL")
    if currency not in {"ALL", "EUR"}:
        raise ValueError("Monedha e pambështetur; përdorni ALL ose EUR")
    vat_rate = percent(project.get("vat_rate", 20), "vat_rate")
    overhead_rate = percent(project.get("overhead_percent", 0), "overhead_percent")
    profit_rate = percent(project.get("profit_percent", 0), "profit_percent")
    discount_rate = percent(project.get("discount_percent", 0), "discount_percent")
    charges = money(decimal_value(project.get("other_charges", 0), "other_charges"))
    base = project.get("calculation_base", "direct")
    if base not in {"direct", "subtotal"}:
        raise ValueError("Baza e llogaritjes duhet të jetë direct ose subtotal")

    subtotal = ZERO
    line_totals = []
    unresolved_rows = []
    for index, row in enumerate(rows):
        identity = row.get("id", index + 1)
        reason = None
        if row.get("decision") != "approved":
            reason = "unapproved"
        elif row.get("unit_price") is None:
            reason = "missing_price"
        elif row.get("currency", currency) != currency:
            reason = "currency_mismatch"
        try:
            quantity = decimal_value(row.get("quantity"), "quantity")
            unit_price = (
                None
                if row.get("unit_price") is None
                else decimal_value(row["unit_price"], "unit_price")
            )
        except ValueError as exc:
            reason = str(exc)
            quantity, unit_price = ZERO, None
        if reason:
            unresolved_rows.append({"row_id": identity, "reason": reason})
            line_totals.append({"row_id": identity, "total": None, "included": False})
            continue
        with localcontext() as ctx:
            ctx.prec = 40
            total = money(quantity * unit_price)
        subtotal += total
        line_totals.append(
            {"row_id": identity, "total": amount_text(total), "included": True}
        )

    overhead = money(subtotal * overhead_rate / HUNDRED)
    profit_base = subtotal if base == "direct" else subtotal + overhead
    profit = money(profit_base * profit_rate / HUNDRED)
    before_discount = subtotal + overhead + profit
    discount = money(before_discount * discount_rate / HUNDRED)
    taxable = before_discount - discount + charges
    vat = money(taxable * vat_rate / HUNDRED)
    total = taxable + vat
    return {
        "currency": currency,
        "subtotal": amount_text(subtotal),
        "direct_cost": amount_text(subtotal),
        "overhead": amount_text(overhead),
        "profit": amount_text(profit),
        "discount": amount_text(discount),
        "other_charges": amount_text(charges),
        "taxable_amount": amount_text(taxable),
        "vat": amount_text(vat),
        "grand_total": amount_text(total),
        "incomplete": bool(unresolved_rows),
        "unresolved_count": len(unresolved_rows),
        "unresolved_rows": unresolved_rows,
        "approved_count": len(rows) - len(unresolved_rows),
        "line_totals": line_totals,
        "calculation_details": {
            "rounding": "ROUND_HALF_UP, 2 decimals per line and per charge",
            "calculation_base": base,
            "overhead_base": amount_text(subtotal),
            "profit_base": amount_text(profit_base),
            "profit_type": "markup",
            "overhead_percent": str(overhead_rate),
            "profit_percent": str(profit_rate),
            "discount_percent": str(discount_rate),
            "vat_rate": str(vat_rate),
            "order": [
                "line_totals",
                "overhead",
                "profit",
                "discount",
                "other_charges",
                "vat",
            ],
            "formula": "((subtotal + overhead + profit) - discount + other_charges) + VAT",
            "component_costs_added": False,
            "base_description": "Approved selected net unit prices; price_kind determines whether these represent purchase, direct, installed or selling prices.",
            "partial_totals": bool(unresolved_rows),
        },
    }


def composite_cost(resources: list[dict]) -> Decimal:
    """Direct resource cost per one work unit, without invented coefficients.

    Coefficients must already be expressed in the resource's own cost unit.
    Callers must use snapshot_price for any unit/currency conversions first.
    """
    if not resources:
        raise ValueError("Kërkohet të paktën një burim")
    total = ZERO
    for resource in resources:
        coefficient = decimal_value(resource.get("coefficient"), "coefficient")
        if coefficient == ZERO:
            raise ValueError("Koeficienti i burimit duhet të jetë pozitiv")
        cost = decimal_value(resource.get("unit_cost"), "unit_cost")
        waste = percent(resource.get("waste_percent", 0), "waste_percent")
        with localcontext() as ctx:
            ctx.prec = 40
            total += coefficient * cost * (Decimal(1) + waste / HUNDRED)
    return total
