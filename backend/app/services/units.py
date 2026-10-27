"""Controlled physical-unit conversion. Factors convert quantity, not price."""

from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping
import unicodedata

# dimension, multiplier relative to the dimension's base unit
_UNITS = {
    "mm": ("length", "0.001"),
    "cm": ("length", "0.01"),
    "m": ("length", "1"),
    "km": ("length", "1000"),
    "mm2": ("area", "0.000001"),
    "cm2": ("area", "0.0001"),
    "m2": ("area", "1"),
    "mm3": ("volume", "0.000000001"),
    "cm3": ("volume", "0.000001"),
    "m3": ("volume", "1"),
    "l": ("volume", "0.001"),
    "g": ("mass", "0.001"),
    "kg": ("mass", "1"),
    "t": ("mass", "1000"),
    "w": ("power", "1"),
    "kw": ("power", "1000"),
    "mw": ("power", "1000000"),
    # Peak DC output is intentionally separate from ordinary power.
    "wp": ("peak_power", "1"),
    "kwp": ("peak_power", "1000"),
    "mwp": ("peak_power", "1000000"),
    "piece": ("count", "1"),
    "set": ("set", "1"),
    "hour": ("time", "1"),
    "day": ("time", "24"),
}
_ALIASES = {
    "cope": "piece",
    "cop": "piece",
    "pcs": "piece",
    "pc": "piece",
    "pieces": "piece",
    "stk": "piece",
    "komplet": "set",
    "komplete": "set",
    "sets": "set",
    "ton": "t",
    "tonne": "t",
    "tonnes": "t",
    "tonelata": "t",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litra": "l",
    "ore": "hour",
    "h": "hour",
    "hr": "hour",
    "dite": "day",
    "d": "day",
    "meter": "m",
    "metra": "m",
    "ml": "m",
    "m.l": "m",
    "sqm": "m2",
    "sq m": "m2",
    "cbm": "m3",
    "cu m": "m3",
}


def normalize_unit(unit: str | None) -> str:
    value = (
        unicodedata.normalize("NFKD", (unit or "").lower())
        .replace("²", "2")
        .replace("³", "3")
    )
    value = (
        "".join(c for c in value if not unicodedata.combining(c))
        .strip()
        .replace("^", "")
    )
    value = re.sub(r"\s+", " ", value).rstrip(".")
    return _ALIASES.get(value, value)


def conversion_factor(
    source: str | None,
    target: str | None,
    custom_rules: Iterable[Mapping] | None = None,
) -> Decimal | None:
    """Return target units per source unit; None means ambiguous/incompatible.

    Custom rules require an explicit approved flag and a strictly positive finite factor.
    The caller must provide only rules authorized for the current user/project.
    """
    source, target = normalize_unit(source), normalize_unit(target)
    if not source or not target:
        return None
    if source == target and source in _UNITS:
        return Decimal(1)
    if source in _UNITS and target in _UNITS:
        dim1, scale1 = _UNITS[source]
        dim2, scale2 = _UNITS[target]
        if dim1 == dim2:
            return Decimal(scale1) / Decimal(scale2)
    for rule in custom_rules or ():
        if rule.get("approved") is not True:
            continue
        if (
            normalize_unit(rule.get("source")) == source
            and normalize_unit(rule.get("target")) == target
        ):
            try:
                factor = Decimal(str(rule["factor"]))
                if factor.is_finite() and factor > 0:
                    return factor
            except (InvalidOperation, KeyError, ValueError, TypeError):
                continue
    return None
