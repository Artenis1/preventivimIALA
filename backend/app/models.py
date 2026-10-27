from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    JSON,
    Boolean,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from .db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PriceItem(Base):
    __tablename__ = "price_items"
    __table_args__ = (UniqueConstraint("owner_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    synonyms: Mapped[str] = mapped_column(Text, default="")
    technical_specs: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(120), default="Të tjera")
    subcategory: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(30))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3), default="ALL")
    price_kind: Mapped[str] = mapped_column(String(20), default="direct")
    supply_included: Mapped[bool] = mapped_column(Boolean, default=False)
    installation_included: Mapped[bool] = mapped_column(Boolean, default=False)
    supplier: Mapped[str] = mapped_column(String(200), default="")
    price_date: Mapped[str] = mapped_column(String(10), default="")
    valid_until: Mapped[str] = mapped_column(String(10), default="")
    vat_included: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=20)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    machinery_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    transport_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    embedding_model: Mapped[str] = mapped_column(String(200), default="")
    embedding: Mapped[list | None] = mapped_column(Vector(), nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    project_type: Mapped[str] = mapped_column(String(100), default="construction")
    currency: Mapped[str] = mapped_column(String(3), default="ALL")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=20)
    overhead_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    profit_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    other_charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    calculation_base: Mapped[str] = mapped_column(String(20), default="direct")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    sheet: Mapped[str | None] = mapped_column(String(255))
    mapping: Mapped[dict | None] = mapped_column(JSON)
    header_row: Mapped[int] = mapped_column(Integer, default=0)
    committed: Mapped[bool] = mapped_column(Boolean, default=False)


class BOQRow(Base):
    __tablename__ = "boq_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"))
    source_row: Mapped[int | None] = mapped_column(Integer)
    item_number: Mapped[str] = mapped_column(String(100), default="")
    code: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    existing_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    existing_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("price_items.id"))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    original_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    price_snapshot: Mapped[dict | None] = mapped_column(JSON)
    match_result: Mapped[dict | None] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MappingDecision(Base):
    __tablename__ = "mapping_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    normalized_description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30))
    item_id: Mapped[int] = mapped_column(ForeignKey("price_items.id"))
    approved: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("price_items.id"), index=True)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    new_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    supplier: Mapped[str] = mapped_column(String(200), default="")
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EstimateVersion(Base):
    __tablename__ = "estimate_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResourceVersion(Base):
    __tablename__ = "resource_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("price_items.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    resources: Mapped[list] = mapped_column(JSON)
    direct_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
