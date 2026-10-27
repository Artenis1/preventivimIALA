import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from .config import get_settings
from .db import get_db
from .models import User, Session
from .schemas import Credentials

router = APIRouter(prefix="/auth", tags=["authentication"])
passwords = PasswordHash.recommended()
# Process-local limiter is complemented by reverse-proxy limits in production.
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, maximum: int, window: int):
    current = time.monotonic()
    queue = _attempts[key]
    while queue and queue[0] < current - window:
        queue.popleft()
    if len(queue) >= maximum:
        raise HTTPException(
            429, "Shumë kërkesa. Provoni më vonë.", headers={"Retry-After": str(window)}
        )
    queue.append(current)
    if len(_attempts) > 10000:
        for old in list(_attempts)[:2000]:
            if not _attempts[old] or _attempts[old][-1] < current - window:
                del _attempts[old]


def public_user(user):
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get("se_session", "")
    if not token:
        raise HTTPException(401, "Identifikohuni për të vazhduar")
    session = db.get(Session, hashlib.sha256(token.encode()).hexdigest())
    if session is None:
        raise HTTPException(401, "Sesioni nuk është i vlefshëm")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(401, "Sesioni ka skaduar")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Sesioni nuk është i vlefshëm")
    return user


def login_session(user, db, response):
    token = secrets.token_urlsafe(48)
    hours = get_settings().session_hours
    db.execute(
        delete(Session).where(
            Session.user_id == user.id, Session.expires_at < datetime.now(timezone.utc)
        )
    )
    db.add(
        Session(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
    )
    db.commit()
    response.set_cookie(
        "se_session",
        token,
        max_age=hours * 3600,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/",
    )
    return public_user(user)


@router.post("/register", status_code=201)
def register(
    data: Credentials,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
):
    rate_limit("register:" + request.client.host, 10, 3600)
    user = User(
        email=data.email.lower(),
        display_name=data.display_name or data.email.split("@")[0],
        password_hash=passwords.hash(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Kjo adresë është e regjistruar")
    return login_session(user, db, response)


@router.post("/login")
def login(
    data: Credentials,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
):
    rate_limit("login:" + request.client.host, 30, 300)
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    # Always verify a hash, reducing user enumeration timing differences.
    valid = passwords.verify(data.password, user.password_hash if user else _dummy_hash)
    if not user or not valid:
        raise HTTPException(401, "Email ose fjalëkalim i pasaktë")
    return login_session(user, db, response)


_dummy_hash = passwords.hash("not-a-real-password-12345")


@router.get("/me")
def me(user=Depends(current_user)):
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    token = request.cookies.get("se_session", "")
    db.execute(
        delete(Session).where(
            Session.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    db.commit()
    response.delete_cookie(
        "se_session",
        path="/",
        secure=get_settings().cookie_secure,
        httponly=True,
        samesite="strict",
    )
