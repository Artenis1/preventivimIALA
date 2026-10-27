from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

Money = Decimal


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class Credentials(Input):
    email: str = Field(
        min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(default="", max_length=120)


class PriceInput(Input):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    synonyms: str = Field(default="", max_length=5000)
    technical_specs: str = Field(default="", max_length=5000)
    category: str = Field(default="Të tjera", max_length=120)
    subcategory: str = Field(default="", max_length=120)
    unit: str = Field(min_length=1, max_length=30)
    price: Money = Field(ge=0, le=Decimal("1000000000000"), decimal_places=6)
    currency: Literal["ALL", "EUR"] = "ALL"
    price_kind: Literal["purchase", "direct", "installed", "selling"] = "direct"
    supply_included: bool = False
    installation_included: bool = False
    supplier: str = Field(default="", max_length=200)
    price_date: str = Field(default="", max_length=10)
    valid_until: str = Field(default="", max_length=10)
    vat_included: bool = False
    vat_rate: Decimal = Field(default=20, ge=0, le=100)
    material_cost: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    labor_cost: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    machinery_cost: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    transport_cost: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    other_cost: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    notes: str = Field(default="", max_length=10000)
    active: bool = True
    reason: str = Field(default="Përditësim manual", max_length=2000)

    @field_validator("code")
    @classmethod
    def canonical_code(cls, value):
        return value.upper()

    @field_validator("price_date", "valid_until")
    @classmethod
    def date_string(cls, value):
        if value:
            from datetime import date

            date.fromisoformat(value)
        return value


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=200)
    client: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    project_type: str = Field(default="construction", max_length=100)
    currency: Literal["ALL", "EUR"] = "ALL"
    vat_rate: Decimal = Field(default=20, ge=0, le=100)
    overhead_percent: Decimal = Field(default=0, ge=0, le=100)
    profit_percent: Decimal = Field(default=0, ge=0, le=100)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    other_charges: Money = Field(default=0, ge=0, le=Decimal("1000000000000"))
    calculation_base: Literal["direct", "subtotal"] = "direct"
    notes: str = Field(default="", max_length=10000)


class ImportInput(Input):
    sheet: str = Field(min_length=1, max_length=255)
    mapping: dict[str, int]
    header_row: int = Field(default=0, ge=0, le=100000)


class RowInput(Input):
    item_id: int | None = None
    decision: Literal["approved", "rejected", "pending"] = "pending"
    unit_price: Money | None = Field(
        default=None, ge=0, le=Decimal("1000000000000"), decimal_places=6
    )
    notes: str = Field(default="", max_length=10000)
    confirm_override: bool = False


class Confirmation(Input):
    confirm: bool = False
    row_ids: list[int] = Field(default_factory=list, max_length=10000)


class Resource(Input):
    item_id: int
    coefficient: Decimal = Field(gt=0, le=Decimal("1000000000"))
    waste_percent: Decimal = Field(default=0, ge=0, le=100)


class ResourcesInput(Input):
    resources: list[Resource] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


class CustomRule(Input):
    source: str = Field(min_length=1, max_length=30)
    target: str = Field(min_length=1, max_length=30)
    factor: Decimal = Field(gt=0, le=Decimal("1000000000"))
    approved: bool


class SettingsInput(Input):
    exchange_rates: dict[str, Decimal] = Field(default_factory=dict)
    custom_unit_rules: list[CustomRule] = Field(default_factory=list, max_length=100)
    high_confidence: float = Field(default=0.93, ge=0.8, le=1)
    medium_confidence: float = Field(default=0.65, ge=0.1, le=0.8)

    @field_validator("exchange_rates")
    @classmethod
    def rates(cls, v):
        for key, value in v.items():
            if key not in ("EUR:ALL", "ALL:EUR") or value <= 0 or value > 1000000:
                raise ValueError("Kursi duhet të jetë pozitiv, EUR:ALL ose ALL:EUR")
        return v


class PriceImportConfirmation(Input):
    preview_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirm: Literal[True]
