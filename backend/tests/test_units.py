from decimal import Decimal
import pytest
from app.services.units import conversion_factor, normalize_unit


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("m", "mm", "1000"),
        ("m²", "cm²", "10000"),
        ("m³", "l", "1000"),
        ("kg", "t", ".001"),
        ("W", "kW", ".001"),
        ("Wp", "kWp", ".001"),
        ("kW", "MW", ".001"),
        ("copë", "pcs", "1"),
        ("cm", "m", ".01"),
    ],
)
def test_controlled_unit_conversion(source, target, expected):
    assert conversion_factor(source, target) == Decimal(expected)


@pytest.mark.parametrize(
    "source,target",
    [("m", "m²"), ("set", "pcs"), ("Wp", "W"), ("", "m"), ("foo", "foo")],
)
def test_incompatible_or_ambiguous_units(source, target):
    assert conversion_factor(source, target) is None


def test_custom_rules_require_explicit_approval_and_positive_finite_factor():
    rule = {"source": "set", "target": "piece", "factor": "5"}
    assert conversion_factor("set", "piece", [rule]) is None
    assert conversion_factor("set", "piece", [dict(rule, approved=True)]) == 5
    assert (
        conversion_factor("set", "piece", [dict(rule, approved=True, factor="NaN")])
        is None
    )
    assert (
        conversion_factor("set", "piece", [dict(rule, approved=True, factor="-1")])
        is None
    )


def test_albanian_unit_alias():
    assert normalize_unit("  COPË  ") == "piece"
