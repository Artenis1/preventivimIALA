from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from openpyxl import Workbook
from .db import get_db
from .auth import current_user, rate_limit
from .models import PriceItem, PriceHistory, ResourceVersion, PriceImportPreview
from .schemas import PriceInput, ResourcesInput, PriceImportConfirmation
from .helpers import asdict, owned, audit, json_safe

router = APIRouter(tags=["prices"])


def history(db, user, item, old, reason):
    db.add(
        PriceHistory(
            owner_id=user.id,
            item_id=item.id,
            old_price=old,
            new_price=item.price,
            currency=item.currency,
            unit=item.unit,
            reason=reason,
            supplier=item.supplier,
            snapshot=asdict(item),
        )
    )


def save_price(db, user, data, item=None):
    values = data.model_dump(exclude={"reason"})
    old = item.price if item else None
    if item:
        for k, v in values.items():
            setattr(item, k, v)
        item.version += 1
        item.embedding = None
    else:
        item = PriceItem(owner_id=user.id, **values)
        db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Kodi ekziston në databazën tuaj")
    history(db, user, item, old, data.reason)
    audit(
        db,
        user,
        "price.update" if old is not None else "price.create",
        "price",
        item.id,
    )
    return item


@router.get("/prices")
def prices(
    q: str = "",
    category: str = "",
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    stmt = select(PriceItem).where(PriceItem.owner_id == user.id)
    if not include_inactive:
        stmt = stmt.where(PriceItem.active.is_(True))
    if q:
        stmt = stmt.where(
            (PriceItem.description.ilike("%" + q[:200] + "%"))
            | (PriceItem.name.ilike("%" + q[:200] + "%"))
            | (PriceItem.code.ilike("%" + q[:200] + "%"))
        )
    if category:
        stmt = stmt.where(PriceItem.category == category)
    return [asdict(x) for x in db.scalars(stmt.order_by(PriceItem.code))]


@router.post("/prices", status_code=201)
def create(data: PriceInput, db: Session = Depends(get_db), user=Depends(current_user)):
    duplicate = db.scalar(
        select(PriceItem.id).where(
            PriceItem.owner_id == user.id,
            func.lower(PriceItem.description) == data.description.lower(),
        )
    )
    item = save_price(db, user, data)
    db.commit()
    return {
        **asdict(item),
        "warnings": ["Përshkrim i mundshëm dublikatë"] if duplicate else [],
    }


@router.get("/prices/history")
def price_history(
    item_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    stmt = select(PriceHistory).where(PriceHistory.owner_id == user.id)
    if item_id:
        stmt = stmt.where(PriceHistory.item_id == item_id)
    return [
        asdict(x) for x in db.scalars(stmt.order_by(PriceHistory.id.desc()).limit(500))
    ]


@router.get("/prices/export")
def export(db: Session = Depends(get_db), user=Depends(current_user)):
    from .services.excel import _safe_text

    wb = Workbook()
    ws = wb.active
    ws.title = "Çmimet"
    fields = list(PriceInput.model_fields)
    ws.append(fields)
    for item in db.scalars(select(PriceItem).where(PriceItem.owner_id == user.id)):
        row = asdict(item)
        row["reason"] = "Import nga Excel"
        ws.append([_safe_text(row.get(f, "")) for f in fields])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="prices.xlsx"'},
    )


async def read_price_upload(file: UploadFile) -> tuple[bytes, str]:
    from .config import get_settings

    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise HTTPException(422, "Përdorni .xlsx, .xlsm ose .xls")
    maximum = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(maximum + 1)
    if len(data) > maximum:
        raise HTTPException(413, "Skedari është shumë i madh")
    return data, filename


def check_import_codes(db, user, result):
    """Return row-specific conflicts without writing any price/history records."""
    rows = result["rows"]
    codes = list({r["values"]["code"] for r in rows if r["status"] == "valid"})
    existing = set()
    for offset in range(0, len(codes), 500):
        existing.update(
            db.scalars(
                select(PriceItem.code).where(
                    PriceItem.owner_id == user.id,
                    PriceItem.code.in_(codes[offset : offset + 500]),
                )
            )
        )
    for row in rows:
        if row["status"] == "valid" and row["values"]["code"] in existing:
            row["status"] = "invalid"
            row["errors"].append(
                {"field": "code", "message": "Kodi ekziston në databazën tuaj"}
            )
    result["valid_count"] = sum(r["status"] == "valid" for r in rows)
    result["error_count"] = sum(r["status"] == "invalid" for r in rows)
    result["can_commit"] = result["valid_count"] > 0 and result["error_count"] == 0
    return result


@router.post("/prices/import/preview")
async def price_import_preview(
    file: UploadFile = File(...),
    sheet: str | None = Form(None, max_length=255),
    mapping: str | None = Form(None, max_length=20000),
    header_row: int | None = Form(None, ge=0, le=49999),
    currency: str = Form("ALL", pattern=r"^(ALL|EUR)$"),
    code_prefix: str = Form("IMPORT", min_length=1, max_length=50),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    from .services.price_import import inspect_prices, preview_prices

    rate_limit(f"price-import:{user.id}", 30, 60)
    data, filename = await read_price_upload(file)
    try:
        mapped = json.loads(mapping) if mapping is not None else None
        if mapped is not None and not isinstance(mapped, dict):
            raise ValueError("Hartëzimi duhet të jetë objekt fushë–kolonë")
        metadata = inspect_prices(data, filename)
        result = preview_prices(
            data,
            filename,
            sheet=sheet,
            mapping=mapped,
            header_row=header_row,
            currency=currency,
            code_prefix=code_prefix,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)[:1000])
    result = check_import_codes(db, user, json_safe(result))
    result.update(metadata)
    token = uuid4().hex
    current = datetime.now(timezone.utc)
    # Bound retained, unsaved previews per account; no project/catalog data removed.
    db.execute(
        delete(PriceImportPreview).where(
            PriceImportPreview.owner_id == user.id,
            PriceImportPreview.expires_at <= current,
        )
    )
    old_ids = list(
        db.scalars(
            select(PriceImportPreview.id)
            .where(PriceImportPreview.owner_id == user.id)
            .order_by(PriceImportPreview.expires_at.desc())
            .offset(9)
        )
    )
    if old_ids:
        db.execute(delete(PriceImportPreview).where(PriceImportPreview.id.in_(old_ids)))
    db.add(
        PriceImportPreview(
            id=token,
            owner_id=user.id,
            payload=result,
            expires_at=current + timedelta(minutes=30),
        )
    )
    db.commit()
    return {**result, "preview_id": token}


@router.post("/prices/import/commit")
def price_import_commit(
    data: PriceImportConfirmation,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    preview = db.scalar(
        select(PriceImportPreview)
        .where(
            PriceImportPreview.id == data.preview_id,
            PriceImportPreview.owner_id == user.id,
        )
        .with_for_update()
    )
    if preview is None:
        raise HTTPException(404, "Pamja paraprake nuk u gjet ose është ruajtur tashmë")
    expiry = preview.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        db.delete(preview)
        db.commit()
        raise HTTPException(410, "Pamja paraprake ka skaduar. Përgatiteni sërish.")
    result = check_import_codes(db, user, json_safe(preview.payload))
    if not result["can_commit"]:
        raise HTTPException(
            422, "Korrigjoni gabimet e rreshtave dhe përgatitni sërish pamjen paraprake"
        )
    for row in result["rows"]:
        if row["status"] == "valid":
            save_price(db, user, PriceInput.model_validate(row["values"]))
    audit(
        db,
        user,
        "price.import",
        "user",
        user.id,
        {"count": result["valid_count"], "sheet": result["sheet"]},
    )
    db.delete(preview)
    db.commit()
    return {
        "imported": result["valid_count"],
        "skipped": result.get("skipped_count", 0),
    }


@router.post("/prices/import")
async def import_prices(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    """Compatibility endpoint; interactive clients use preview + explicit commit."""
    from .services.price_import import preview_prices

    data, filename = await read_price_upload(file)
    try:
        result = check_import_codes(db, user, json_safe(preview_prices(data, filename)))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)[:1000])
    numeric_review = [r for r in result["rows"] if r.get("numeric_review_required")]
    if numeric_review:
        locations = ", ".join(str(r["source_row"]) for r in numeric_review[:10])
        raise HTTPException(
            422,
            f"Rreshtat {locations}: ndarës numerikë të paqartë. Përdorni pamjen paraprake dhe konfirmoni çmimet e interpretuara.",
        )
    if not result["can_commit"]:
        errors = [
            {"row": row["source_row"], **error}
            for row in result["rows"]
            for error in row["errors"]
        ]
        conflict = any(
            e["field"] == "code" and "ekziston" in e["message"] for e in errors
        )
        summary = "; ".join(
            f"Rreshti {e['row']}, {e['field']}: {e['message']}" for e in errors[:10]
        )
        raise HTTPException(
            409 if conflict else 422, summary or "Nuk ka rreshta të vlefshëm për import"
        )
    for row in result["rows"]:
        if row["status"] == "valid":
            save_price(db, user, PriceInput.model_validate(row["values"]))
    db.commit()
    return {"imported": result["valid_count"]}


@router.put("/prices/{item_id}")
def update(
    item_id: int,
    data: PriceInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    item = owned(db, PriceItem, item_id, user)
    item = save_price(db, user, data, item)
    db.commit()
    return asdict(item)


@router.delete("/prices/{item_id}", status_code=204)
def archive(item_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    item = owned(db, PriceItem, item_id, user)
    item.active = False
    audit(db, user, "price.archive", "price", item_id)
    db.commit()


@router.get("/prices/{item_id}/resources")
def get_resources(
    item_id: int, db: Session = Depends(get_db), user=Depends(current_user)
):
    owned(db, PriceItem, item_id, user)
    return [
        asdict(x)
        for x in db.scalars(
            select(ResourceVersion)
            .where(ResourceVersion.item_id == item_id)
            .order_by(ResourceVersion.number.desc())
        )
    ]


@router.put("/prices/{item_id}/resources")
def resources(
    item_id: int,
    data: ResourcesInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    from .services.calculations import composite_cost, convert_money

    item = db.scalar(
        select(PriceItem)
        .where(PriceItem.id == item_id, PriceItem.owner_id == user.id)
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "Nuk u gjet")
    resources = []
    for row in data.resources:
        if row.item_id == item_id:
            raise HTTPException(422, "Zëri nuk mund të jetë burim i vetvetes")
        resource = owned(db, PriceItem, row.item_id, user)
        if not resource.active:
            raise HTTPException(422, "Burimi është i arkivuar")
        cost = (
            resource.price / (1 + resource.vat_rate / 100)
            if resource.vat_included
            else resource.price
        )
        try:
            cost = convert_money(
                cost,
                resource.currency,
                item.currency,
                user.settings.get("exchange_rates", {}),
            )
        except ValueError as e:
            raise HTTPException(422, str(e))
        resources.append(
            {
                **row.model_dump(mode="json"),
                "unit_cost": str(cost),
                "unit": resource.unit,
                "code": resource.code,
                "price_version": resource.version,
                "original_price": str(resource.price),
                "original_currency": resource.currency,
                "vat_included": resource.vat_included,
                "vat_rate": str(resource.vat_rate),
                "converted_currency": item.currency,
            }
        )
    try:
        cost = composite_cost(resources).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        if cost > Decimal("1000000000000"):
            raise ValueError("Kostoja e përbërë tejkalon kufirin e çmimit")
    except (ValueError, InvalidOperation) as e:
        raise HTTPException(422, str(e))
    number = (
        db.scalar(
            select(func.max(ResourceVersion.number)).where(
                ResourceVersion.item_id == item_id
            )
        )
        or 0
    ) + 1
    version = ResourceVersion(
        item_id=item_id,
        number=number,
        resources=json_safe(resources),
        direct_cost=cost,
        reason=data.reason,
    )
    db.add(version)
    old = item.price
    item.price = cost
    item.vat_included = False
    item.price_kind = "direct"
    item.version += 1
    item.embedding = None
    history(db, user, item, old, data.reason)
    audit(db, user, "resources.update", "price", item_id, {"version": number})
    db.commit()
    return asdict(version)


@router.post("/prices/{item_id}/attachments", status_code=201)
async def attach(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    import uuid
    from pathlib import Path
    from .config import get_settings

    item = owned(db, PriceItem, item_id, user)
    data = await file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Maksimumi 5 MB për dokument")
    filename = Path(file.filename or "").name[:200]
    suffix = Path(filename).suffix.lower()
    signatures = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }
    if suffix not in signatures or not data.startswith(signatures[suffix]):
        raise HTTPException(422, "Vetëm PDF, PNG ose JPEG të vlefshme")
    if len(item.attachments) >= 20:
        raise HTTPException(422, "Maksimumi 20 dokumente për çmim")
    token = uuid.uuid4().hex
    storage = Path(get_settings().storage_dir).resolve()
    storage.mkdir(parents=True, exist_ok=True)
    (storage / token).write_bytes(data)
    item.attachments = [
        *item.attachments,
        {"id": token, "filename": filename, "size": len(data), "suffix": suffix},
    ]
    audit(db, user, "price.attachment", "price", item.id, {"filename": filename})
    db.commit()
    return item.attachments[-1]


@router.get("/prices/{item_id}/attachments/{attachment_id}")
def attachment(
    item_id: int,
    attachment_id: str,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    import re
    from pathlib import Path
    from fastapi.responses import FileResponse
    from .config import get_settings

    item = owned(db, PriceItem, item_id, user)
    entry = next((a for a in item.attachments if a["id"] == attachment_id), None)
    if not entry or not re.fullmatch("[a-f0-9]{32}", attachment_id):
        raise HTTPException(404, "Nuk u gjet")
    path = Path(get_settings().storage_dir).resolve() / attachment_id
    if not path.is_file():
        raise HTTPException(404, "Dokumenti mungon")
    return FileResponse(
        path,
        filename=entry["filename"],
        media_type="application/octet-stream",
        headers={"Content-Security-Policy": "sandbox"},
    )
