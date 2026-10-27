import json
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.inspection import inspect
from fastapi import HTTPException
from .models import Audit


def json_safe(value):
    def encode(x):
        if isinstance(x, (Decimal, datetime, date)):
            return str(x)
        raise TypeError(type(x).__name__)

    return json.loads(json.dumps(value, default=encode))


def asdict(model):
    return json_safe(
        {
            column.key: getattr(model, column.key)
            for column in inspect(model).mapper.column_attrs
            if column.key not in ("password_hash", "embedding")
        }
    )


def owned(db, model, entity_id, user):
    item = db.get(model, entity_id)
    if item is None or item.owner_id != user.id:
        raise HTTPException(404, "Nuk u gjet")
    return item


def editable(project):
    if project.status == "finalized":
        raise HTTPException(
            409, "Preventivi është finalizuar. Rihapeni me konfirmim për ndryshime."
        )


def audit(db, user, action, entity, entity_id, details=None):
    db.add(
        Audit(
            owner_id=user.id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=json_safe(details or {}),
        )
    )
