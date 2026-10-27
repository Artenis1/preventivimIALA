from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from openpyxl import Workbook
from .db import get_db
from .auth import current_user
from .models import PriceItem, PriceHistory, ResourceVersion
from .schemas import PriceInput, ResourcesInput
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


@router.post("/prices/import")
async def import_prices(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    from .services.excel import _open
    from .config import get_settings

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, "Përdorni .xlsx ose .xlsm")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Skedari është shumë i madh")
    wb = None
    try:
        wb = _open(data)
        ws = wb.active
        iterator = ws.iter_rows(values_only=True)
        headers = [str(v or "").strip() for v in next(iterator)]
        named_headers = [header for header in headers if header]
        if len(named_headers) != len(set(named_headers)):
            raise ValueError("Kolona me emra të dyfishuar")
        if not {"code", "name", "description", "unit", "price"}.issubset(headers):
            raise ValueError(
                "Importoni formatin e eksportit me kolonat code,name,description,unit,price"
            )
        validated = []
        for number, row in enumerate(iterator, 2):
            if not any(v is not None for v in row):
                continue
            values = {
                k: v
                for k, v in zip(headers, row)
                if k in PriceInput.model_fields and v is not None
            }
            validated.append(PriceInput.model_validate(values))
            if len(validated) > 10000:
                raise ValueError("Maksimumi 10000 çmime")
        wb.close()
        for value in validated:
            save_price(db, user, value)
        db.commit()
        return {"imported": len(validated)}
    except (ValueError, ValidationError, StopIteration) as e:
        db.rollback()
        raise HTTPException(422, str(e)[:1000])
    finally:
        if wb is not None:
            wb.close()


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
