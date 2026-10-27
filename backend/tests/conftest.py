import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/smartestimate-tests-default.db")
os.environ.setdefault("STORAGE_DIR", "/tmp/smartestimate-test-storage")
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, get_db
from app.main import app
from app.auth import _attempts


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    _attempts.clear()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def user(client):
    result = client.post(
        "/api/auth/register",
        json={
            "email": "engineer@example.com",
            "password": "secure-password-123",
            "display_name": "Inxhinier",
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


@pytest.fixture
def price(client, user):
    result = client.post(
        "/api/prices",
        json={
            "code": "C25",
            "name": "Beton",
            "description": "Furnizim beton C25/30",
            "unit": "m³",
            "price": "100",
            "currency": "EUR",
            "supply_included": True,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()
