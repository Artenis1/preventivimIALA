import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .auth import current_user, rate_limit
from .config import get_settings
from .models import (
    Project,
    BOQRow,
    Upload,
    PriceItem,
    MappingDecision,
    EstimateVersion,
    Audit,
)
from .schemas import ProjectInput, ImportInput, RowInput, Confirmation, SettingsInput
from .helpers import asdict, owned, editable, audit, json_safe
from .services.excel import (
    inspect_workbook,
    import_rows,
    export_standard,
    export_original,
)
from .services.calculations import calculate_estimate, snapshot_price
from .services.matching import (
    match_row,
    normalize_text,
    embed_text,
    item_text,
    semantic_candidates,
)

router = APIRouter(tags=["projects"])


def rows_for(db, project):
    return list(
        db.scalars(
            select(BOQRow).where(BOQRow.project_id == project.id).order_by(BOQRow.id)
        )
    )


def payload(db, project):
    rows = [asdict(x) for x in rows_for(db, project)]
    totals = calculate_estimate(asdict(project), rows)
    line_totals = {x["row_id"]: x["total"] for x in totals["line_totals"]}
    for row in rows:
        row["total"] = line_totals.get(row["id"])
    return {
        **asdict(project),
        "project": asdict(project),
        "rows": rows,
        "totals": totals,
        "versions": [
            asdict(v)
            for v in db.scalars(
                select(EstimateVersion)
                .where(EstimateVersion.project_id == project.id)
                .order_by(EstimateVersion.number.desc())
            )
        ],
    }


def lock_project(db, project_id, user):
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == user.id)
        .with_for_update()
    )
    if project is None:
        raise HTTPException(404, "Nuk u gjet")
    return project


@router.get("/projects")
def projects(db: Session = Depends(get_db), user=Depends(current_user)):
    return [
        asdict(x)
        for x in db.scalars(
            select(Project)
            .where(Project.owner_id == user.id)
            .order_by(Project.id.desc())
        )
    ]


@router.post("/projects", status_code=201)
def create_project(
    data: ProjectInput, db: Session = Depends(get_db), user=Depends(current_user)
):
    project = Project(owner_id=user.id, **data.model_dump())
    db.add(project)
    db.flush()
    audit(db, user, "project.create", "project", project.id)
    db.commit()
    return asdict(project)


@router.get("/projects/{project_id}")
def get_project(
    project_id: int, db: Session = Depends(get_db), user=Depends(current_user)
):
    return payload(db, owned(db, Project, project_id, user))


@router.patch("/projects/{project_id}")
def edit_project(
    project_id: int,
    data: ProjectInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = lock_project(db, project_id, user)
    editable(project)
    if project.currency != data.currency and any(
        r.unit_price is not None for r in rows_for(db, project)
    ):
        raise HTTPException(
            409,
            "Monedha nuk ndryshohet pasi janë vendosur çmimet. Krijoni një projekt të ri.",
        )
    before = asdict(project)
    for k, v in data.model_dump().items():
        setattr(project, k, v)
    audit(
        db,
        user,
        "project.update",
        "project",
        project.id,
        {"before": before, "after": asdict(project)},
    )
    db.commit()
    return asdict(project)


@router.post("/projects/{project_id}/imports")
async def upload(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = lock_project(db, project_id, user)
    editable(project)
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, "Përdorni .xlsx ose .xlsm; makrot nuk ekzekutohen")
    maximum = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(maximum + 1)
    if len(data) > maximum:
        raise HTTPException(413, "Skedari është shumë i madh")
    try:
        preview = inspect_workbook(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    storage = Path(get_settings().storage_dir).resolve()
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / (uuid.uuid4().hex + ".xlsx")
    path.write_bytes(data)
    entry = Upload(
        project_id=project.id, path=str(path), filename=Path(file.filename).name[:255]
    )
    db.add(entry)
    db.flush()
    audit(db, user, "boq.upload", "project", project.id)
    db.commit()
    return {**preview, "upload_id": entry.id, "id": entry.id}


@router.post("/projects/{project_id}/imports/{upload_id}/commit")
def commit_upload(
    project_id: int,
    upload_id: int,
    data: ImportInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = lock_project(db, project_id, user)
    editable(project)
    upload = db.get(Upload, upload_id)
    if not upload or upload.project_id != project.id:
        raise HTTPException(404, "Nuk u gjet")
    if upload.committed:
        raise HTTPException(409, "Ky skedar është importuar tashmë")
    try:
        result = import_rows(
            Path(upload.path).read_bytes(), data.sheet, data.mapping, data.header_row
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not result["rows"]:
        raise HTTPException(
            422,
            {"message": "Nuk ka rreshta të vlefshëm", "rejected": result["rejected"]},
        )
    for row in result["rows"]:
        for field in ("quantity", "existing_unit_price", "existing_total"):
            if row.get(field) is None:
                continue
            value = Decimal(str(row[field]))
            if not value.is_finite() or value < 0 or value > Decimal("1000000000000"):
                raise HTTPException(
                    422,
                    f"Rreshti {row.get('source_row')}: {field} duhet të jetë jo negativ dhe brenda kufirit",
                )
            if value != value.quantize(Decimal("0.000001")):
                raise HTTPException(
                    422,
                    f"Rreshti {row.get('source_row')}: {field} mbështet deri në 6 shifra dhjetore; korrigjoni skedarin pa humbje të heshtur",
                )
        db.add(BOQRow(project_id=project.id, upload_id=upload.id, **row))
    upload.sheet = data.sheet
    upload.mapping = data.mapping
    upload.header_row = data.header_row
    upload.committed = True
    audit(
        db,
        user,
        "boq.import",
        "project",
        project.id,
        {
            "upload_id": upload.id,
            "rows": len(result["rows"]),
            "rejected": result["rejected"],
        },
    )
    db.commit()
    return {
        "imported": len(result["rows"]),
        "rejected": result["rejected"],
        **payload(db, project),
    }


@router.post("/projects/{project_id}/match")
async def matching(
    project_id: int, db: Session = Depends(get_db), user=Depends(current_user)
):
    rate_limit(f"ai:{user.id}", 10, 60)
    project = lock_project(db, project_id, user)
    editable(project)
    items = list(
        db.scalars(
            select(PriceItem).where(
                PriceItem.owner_id == user.id, PriceItem.active.is_(True)
            )
        )
    )
    config = {**get_settings().model_dump(), **user.settings}
    mappings = [
        asdict(x)
        for x in db.scalars(
            select(MappingDecision).where(MappingDecision.owner_id == user.id)
        )
    ]
    semantic_enabled = bool(config.get("ai_api_key") and config.get("embedding_model"))
    embedding_error = False
    if semantic_enabled:
        for item in items:
            if item.embedding is None or item.embedding_model != config.get(
                "embedding_model"
            ):
                try:
                    item.embedding = await embed_text(item_text(asdict(item)), config)
                    item.embedding_model = config["embedding_model"]
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    embedding_error = True
                    break
        db.flush()
    changed = 0
    for row in rows_for(db, project):
        # Keep every explicit human decision, including rejection, until manually revised.
        if row.decision != "pending":
            continue
        candidates = [
            {
                **asdict(item),
                "_embedding": item.embedding.tolist()
                if hasattr(item.embedding, "tolist")
                else item.embedding,
            }
            for item in items
        ]
        if (
            semantic_enabled
            and not embedding_error
            and db.get_bind().dialect.name == "postgresql"
        ):
            try:
                vector = await embed_text(row.description, config)
                ranked = semantic_candidates(db, user.id, vector)
                ids = {entry["id"] for entry in ranked}
                # Always retain exact/normalized candidates in addition to vector retrieval.
                candidates = [
                    c
                    for c in candidates
                    if c["id"] in ids
                    or (
                        row.code
                        and normalize_text(c["code"]) == normalize_text(row.code)
                    )
                    or normalize_text(c["description"])
                    == normalize_text(row.description)
                ]
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                embedding_error = True
        row_data = asdict(row)
        if semantic_enabled and not embedding_error and "vector" in locals():
            row_data["_embedding"] = vector
        result = await match_row(row_data, candidates, mappings, config)
        if embedding_error:
            result["ai_unavailable"] = True
        if result["suggested_item_id"]:
            item = next(i for i in items if i.id == result["suggested_item_id"])
            try:
                snap = price_snapshot(item, row, user, project)
                result["suggested_unit_price"] = snap["unit_price"]
                result["currency"] = project.currency
                result["suggested_item_version"] = item.version
                if snap.get("warnings"):
                    result["discrepancies"] += snap["warnings"]
                    result["classification"] = "medium"
            except ValueError as e:
                result["discrepancies"].append(str(e))
                result["classification"] = "medium"
                result["suggested_unit_price"] = None
        row.match_result = json_safe(result)
        changed += 1
    audit(db, user, "matching.suggest", "project", project.id, {"rows": changed})
    db.commit()
    return {"matched": changed, **payload(db, project)}


def row_of(db, project, row_id):
    row = db.get(BOQRow, row_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "Nuk u gjet")
    return row


def price_snapshot(item, row, user, project):
    snapshot = snapshot_price(
        asdict(item),
        row.unit,
        project.currency,
        user.settings.get("exchange_rates", {}),
        user.settings.get("custom_unit_rules", []),
    )
    exact = Decimal(snapshot["unit_price"])
    if exact > Decimal("1000000000000"):
        raise ValueError("Çmimi i konvertuar tejkalon kufirin e lejuar")
    rounded = exact.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    if exact > 0 and rounded == 0:
        raise ValueError(
            "Çmimi i konvertuar tejkalon kufijtë e saktësisë së ruajtjes; kërkohet njësi ose çmim manual tjetër"
        )
    snapshot["unrounded_unit_price"] = str(exact)
    snapshot["unit_price"] = str(rounded)
    snapshot["unit_price_rounding"] = "ROUND_HALF_UP, 6 decimal places"
    return snapshot


def approve(db, user, project, row, item, override=None, notes=""):
    try:
        snapshot = price_snapshot(item, row, user, project)
    except ValueError as e:
        raise HTTPException(422, str(e))
    row.item_id = item.id
    row.price_snapshot = snapshot
    row.original_unit_price = Decimal(snapshot["unit_price"])
    row.unit_price = override if override is not None else row.original_unit_price
    row.decision = "approved"
    row.approved_by = user.id
    row.approved_at = datetime.now(timezone.utc)
    row.notes = notes
    db.add(
        MappingDecision(
            owner_id=user.id,
            normalized_description=normalize_text(row.description),
            unit=row.unit,
            item_id=item.id,
            approved=True,
        )
    )


@router.patch("/projects/{project_id}/rows/{row_id}")
def decide(
    project_id: int,
    row_id: int,
    data: RowInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = lock_project(db, project_id, user)
    editable(project)
    row = row_of(db, project, row_id)
    if row.decision in ("approved", "rejected") and not data.confirm_override:
        raise HTTPException(409, "Konfirmoni ndryshimin e vendimit të mëparshëm")
    before = asdict(row)
    # PATCH fields are optional; editing notes must not implicitly reset a decision.
    decision = data.decision if "decision" in data.model_fields_set else row.decision
    notes = data.notes if "notes" in data.model_fields_set else row.notes
    if decision == "approved":
        explicit_item = "item_id" in data.model_fields_set
        item_id = (
            data.item_id
            if explicit_item
            else (
                row.item_id
                if row.decision == "approved"
                else (row.item_id or (row.match_result or {}).get("suggested_item_id"))
            )
        )
        # A retained approval is a frozen quote. Catalog refresh is a separate,
        # previewable operation and must never happen while merely editing it.
        if row.decision == "approved" and item_id == row.item_id:
            if data.unit_price is not None:
                row.unit_price = data.unit_price
            row.notes = notes
            row.approved_by = user.id
            row.approved_at = datetime.now(timezone.utc)
        elif item_id:
            item = owned(db, PriceItem, item_id, user)
            approve(db, user, project, row, item, data.unit_price, notes)
        elif data.unit_price is not None:
            row.item_id = None
            row.unit_price = data.unit_price
            row.original_unit_price = row.existing_unit_price
            row.price_snapshot = {
                "manual": True,
                "currency": project.currency,
                "unit": row.unit,
                "unit_price": str(data.unit_price),
            }
            row.decision = "approved"
            row.approved_by = user.id
            row.approved_at = datetime.now(timezone.utc)
            row.notes = notes
        else:
            raise HTTPException(422, "Zgjidhni çmim ose vendosni një çmim manual")
    else:
        rejected_item = (
            data.item_id
            or row.item_id
            or (row.match_result or {}).get("suggested_item_id")
        )
        if decision == "rejected" and rejected_item:
            owned(db, PriceItem, rejected_item, user)
            db.add(
                MappingDecision(
                    owner_id=user.id,
                    normalized_description=normalize_text(row.description),
                    unit=row.unit,
                    item_id=rejected_item,
                    approved=False,
                )
            )
        row.decision = decision
        row.unit_price = None
        row.item_id = None
        row.price_snapshot = None
        row.approved_by = None
        row.approved_at = None
        row.notes = notes
    audit(
        db,
        user,
        "matching." + decision,
        "row",
        row.id,
        {"before": before, "after": asdict(row)},
    )
    db.commit()
    return asdict(row)


def eligible(db, user, project):
    output = []
    for row in rows_for(db, project):
        result = row.match_result or {}
        if (
            row.decision != "pending"
            or result.get("classification") != "high"
            or result.get("discrepancies")
            or result.get("suggested_unit_price") is None
        ):
            continue
        item = db.get(PriceItem, result.get("suggested_item_id"))
        if (
            not item
            or item.owner_id != user.id
            or not item.active
            or item.version != result.get("suggested_item_version")
        ):
            continue
        try:
            snapshot = price_snapshot(item, row, user, project)
            if snapshot.get("warnings") or Decimal(snapshot["unit_price"]) != Decimal(
                str(result["suggested_unit_price"])
            ):
                continue
        except ValueError:
            continue
        output.append(row)
    return output


@router.get("/projects/{project_id}/approve-preview")
def approval_preview(
    project_id: int, db: Session = Depends(get_db), user=Depends(current_user)
):
    project = owned(db, Project, project_id, user)
    return {
        "rows": [asdict(x) for x in eligible(db, user, project)],
        "confirmation_required": True,
    }


@router.post("/projects/{project_id}/approve-bulk")
def bulk(
    project_id: int,
    data: Confirmation,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    if not data.confirm:
        raise HTTPException(422, "Kërkohet konfirmim")
    project = lock_project(db, project_id, user)
    editable(project)
    candidates = {x.id: x for x in eligible(db, user, project)}
    if (
        not data.row_ids
        or len(set(data.row_ids)) != len(data.row_ids)
        or not set(data.row_ids).issubset(candidates)
    ):
        raise HTTPException(409, "Lista ka ndryshuar. Hapni sërish pamjen paraprake.")
    for row_id in data.row_ids:
        row = candidates[row_id]
        item = owned(db, PriceItem, row.match_result["suggested_item_id"], user)
        approve(db, user, project, row, item)
    audit(
        db,
        user,
        "matching.bulk_approve",
        "project",
        project.id,
        {"row_ids": data.row_ids},
    )
    db.commit()
    return payload(db, project)


@router.post("/projects/{project_id}/finalize")
def finalize(
    project_id: int,
    data: Confirmation,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    if not data.confirm:
        raise HTTPException(422, "Kërkohet konfirmim")
    project = lock_project(db, project_id, user)
    editable(project)
    snapshot = payload(db, project)
    if not snapshot["rows"] or snapshot["totals"]["incomplete"]:
        raise HTTPException(
            409, "Zgjidhni dhe miratoni të gjithë rreshtat para finalizimit"
        )
    number = (
        db.scalar(
            select(func.max(EstimateVersion.number)).where(
                EstimateVersion.project_id == project.id
            )
        )
        or 0
    ) + 1
    project.status = "finalized"
    snapshot["status"] = "finalized"
    snapshot["project"]["status"] = "finalized"
    snapshot.pop("versions", None)
    db.add(EstimateVersion(project_id=project.id, number=number, snapshot=snapshot))
    audit(db, user, "estimate.finalize", "project", project.id, {"version": number})
    db.commit()
    return payload(db, project)


@router.post("/projects/{project_id}/reopen")
def reopen(
    project_id: int,
    data: Confirmation,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    if not data.confirm:
        raise HTTPException(422, "Kërkohet konfirmim")
    project = lock_project(db, project_id, user)
    project.status = "draft"
    audit(db, user, "estimate.reopen", "project", project.id)
    db.commit()
    return payload(db, project)


@router.post("/projects/{project_id}/refresh-prices")
def refresh_prices(
    project_id: int,
    data: Confirmation,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = lock_project(db, project_id, user)
    editable(project)
    differences = []
    for row in rows_for(db, project):
        if not row.item_id or row.decision != "approved":
            continue
        item = owned(db, PriceItem, row.item_id, user)
        try:
            snapshot = price_snapshot(item, row, user, project)
        except ValueError as e:
            raise HTTPException(422, str(e))
        differences.append(
            {
                "row_id": row.id,
                "old_price": str(row.unit_price),
                "new_price": snapshot["unit_price"],
                "warnings": snapshot.get("warnings", []),
            }
        )
        if data.confirm:
            row.original_unit_price = Decimal(snapshot["unit_price"])
            row.unit_price = row.original_unit_price
            row.price_snapshot = snapshot
    if data.confirm:
        audit(
            db,
            user,
            "estimate.refresh_prices",
            "project",
            project.id,
            {"differences": differences},
        )
        db.commit()
    return {"differences": differences, "applied": data.confirm}


@router.get("/projects/{project_id}/versions")
def versions(
    project_id: int, db: Session = Depends(get_db), user=Depends(current_user)
):
    return payload(db, owned(db, Project, project_id, user))["versions"]


@router.get("/projects/{project_id}/compare")
def compare(
    project_id: int,
    left: int,
    right: int,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    owned(db, Project, project_id, user)
    a = db.scalar(
        select(EstimateVersion).where(
            EstimateVersion.project_id == project_id, EstimateVersion.number == left
        )
    )
    b = db.scalar(
        select(EstimateVersion).where(
            EstimateVersion.project_id == project_id, EstimateVersion.number == right
        )
    )
    if not a or not b:
        raise HTTPException(404, "Versioni nuk u gjet")
    left_currency = a.snapshot["totals"]["currency"]
    right_currency = b.snapshot["totals"]["currency"]
    same_currency = left_currency == right_currency
    old_rows = {row["id"]: row for row in a.snapshot["rows"]}
    new_rows = {row["id"]: row for row in b.snapshot["rows"]}
    differences = []
    for row_id in sorted(old_rows.keys() | new_rows.keys()):
        old = old_rows.get(row_id)
        new = new_rows.get(row_id)
        changed_fields = [
            field
            for field in (
                "description",
                "unit",
                "quantity",
                "unit_price",
                "total",
                "item_id",
                "decision",
                "notes",
            )
            if (old or {}).get(field) != (new or {}).get(field)
        ]
        if old is not None and new is not None and not changed_fields:
            continue

        def delta(field):
            if not same_currency:
                return None
            previous = (old or {}).get(field)
            current = (new or {}).get(field)
            if old is None:
                previous = "0"
            if new is None:
                current = "0"
            return (
                str(Decimal(str(current)) - Decimal(str(previous)))
                if current is not None and previous is not None
                else None
            )

        differences.append(
            {
                "row_id": row_id,
                "item_number": (new or old)["item_number"],
                "description": (new or old)["description"],
                "change": "added"
                if old is None
                else ("removed" if new is None else "changed"),
                "changed_fields": changed_fields,
                "old_quantity": (old or {}).get("quantity"),
                "new_quantity": (new or {}).get("quantity"),
                "old_unit": (old or {}).get("unit"),
                "new_unit": (new or {}).get("unit"),
                "old_unit_price": (old or {}).get("unit_price"),
                "new_unit_price": (new or {}).get("unit_price"),
                "unit_price_difference": delta("unit_price"),
                "old_total": (old or {}).get("total"),
                "new_total": (new or {}).get("total"),
                "total_difference": delta("total"),
                "old_item_id": (old or {}).get("item_id"),
                "new_item_id": (new or {}).get("item_id"),
            }
        )
    return {
        "left": asdict(a),
        "right": asdict(b),
        "currency": left_currency if same_currency else None,
        "left_currency": left_currency,
        "right_currency": right_currency,
        "comparable_currency": same_currency,
        "grand_total_difference": str(
            Decimal(b.snapshot["totals"]["grand_total"])
            - Decimal(a.snapshot["totals"]["grand_total"])
        )
        if same_currency
        else None,
        "row_differences": differences,
        "changed_row_count": len(differences),
        "warnings": []
        if same_currency
        else [
            "Versionet kanë monedha të ndryshme; diferencat monetare nuk kombinohen."
        ],
    }


@router.get("/projects/{project_id}/export")
def export(
    project_id: int,
    format: str = "standard",
    upload_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    project = owned(db, Project, project_id, user)
    snapshot = payload(db, project)
    rows = snapshot["rows"]
    for row in rows:
        row["matching_warnings"] = (row.get("match_result") or {}).get(
            "discrepancies", []
        )
    if format == "standard":
        data = export_standard(asdict(project), rows, snapshot["totals"])
    elif format == "original":
        uploads = list(
            db.scalars(
                select(Upload).where(
                    Upload.project_id == project.id, Upload.committed.is_(True)
                )
            )
        )
        if upload_id:
            uploads = [u for u in uploads if u.id == upload_id]
        if len(uploads) != 1:
            raise HTTPException(422, "Zgjidhni upload_id kur projekti ka disa skedarë")
        upload = uploads[0]
        data = export_original(
            Path(upload.path).read_bytes(),
            upload.sheet,
            [r for r in rows if r["upload_id"] == upload.id],
            upload.mapping,
            upload.header_row,
            project=asdict(project),
            totals=snapshot["totals"],
        )
    else:
        raise HTTPException(422, "Formati nuk mbështetet")
    audit(db, user, "estimate.export", "project", project.id, {"format": format})
    db.commit()
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="estimate-{project.id}.xlsx"'
        },
    )


@router.get("/settings")
def settings(user=Depends(current_user)):
    return {
        **SettingsInput().model_dump(mode="json"),
        **user.settings,
        "ai_available": bool(get_settings().ai_api_key),
        "ai_model": get_settings().ai_model,
        "embedding_model": get_settings().embedding_model,
    }


@router.put("/settings")
def update_settings(
    data: SettingsInput, db: Session = Depends(get_db), user=Depends(current_user)
):
    if data.medium_confidence >= data.high_confidence:
        raise HTTPException(422, "Pragjet nuk janë të renditura")
    user.settings = data.model_dump(mode="json")
    audit(db, user, "settings.update", "user", user.id)
    db.commit()
    return user.settings


@router.get("/audit")
def audit_log(db: Session = Depends(get_db), user=Depends(current_user)):
    return [
        asdict(x)
        for x in db.scalars(
            select(Audit)
            .where(Audit.owner_id == user.id)
            .order_by(Audit.id.desc())
            .limit(500)
        )
    ]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(current_user)):
    from .models import PriceHistory

    projects = list(db.scalars(select(Project).where(Project.owner_id == user.id)))
    project_ids = [p.id for p in projects]
    rows = (
        list(db.scalars(select(BOQRow).where(BOQRow.project_id.in_(project_ids))))
        if project_ids
        else []
    )
    values = {"ALL": Decimal(0), "EUR": Decimal(0)}
    for project in projects:
        values[project.currency] += Decimal(
            payload(db, project)["totals"]["grand_total"]
        )
    frequent = {}
    for row in rows:
        if row.item_id and row.decision == "approved":
            frequent[row.item_id] = frequent.get(row.item_id, 0) + 1
    return {
        "total_projects": len(projects),
        "draft_estimates": sum(p.status == "draft" for p in projects),
        "finalized_estimates": sum(p.status == "finalized" for p in projects),
        "total_values": json_safe(values),
        "unmatched_rows": sum(
            not (r.match_result or {}).get("suggested_item_id")
            and r.decision != "approved"
            for r in rows
        ),
        "awaiting_approval": sum(r.decision == "pending" for r in rows),
        "total_prices": db.scalar(
            select(func.count(PriceItem.id)).where(
                PriceItem.owner_id == user.id, PriceItem.active.is_(True)
            )
        ),
        "recent_prices": [
            asdict(x)
            for x in db.scalars(
                select(PriceHistory)
                .where(PriceHistory.owner_id == user.id)
                .order_by(PriceHistory.id.desc())
                .limit(10)
            )
        ],
        "frequently_used": [
            {"item_id": k, "count": v, "name": db.get(PriceItem, k).name}
            for k, v in sorted(frequent.items(), key=lambda pair: -pair[1])[:10]
        ],
    }
