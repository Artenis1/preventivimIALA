"""Optional real-PostgreSQL integration checks.

Run migrations first, then:
TEST_POSTGRES_URL=postgresql+psycopg://... python -m pytest tests/test_postgres.py
All data written by these tests is rolled back; existing tables are never dropped.
The provider contract tests run without PostgreSQL or network access.
"""

from __future__ import annotations

import json
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.models import PriceItem, User
from app.services.matching import (
    MatchingConfig,
    compare_with_ai,
    embed_text,
    embed_texts,
    semantic_candidates,
)


@pytest.fixture
def postgres_session():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL not set; real pgvector integration was not run")
    engine = create_engine(url, pool_pre_ping=True)
    assert engine.dialect.name == "postgresql", "TEST_POSTGRES_URL must use PostgreSQL"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            with Session(bind=connection) as session:
                yield session
            transaction.rollback()
    finally:
        engine.dispose()


def add_owner(session):
    owner = User(
        email=f"postgres-test-{uuid4().hex}@example.com",
        display_name="Test",
        password_hash="not-a-login-hash",
    )
    session.add(owner)
    session.flush()
    return owner


def add_price(session, owner, code, vector, active=True):
    price = PriceItem(
        owner_id=owner.id,
        code=code,
        name=code,
        description="Montim konstruksioni FV",
        unit="kg",
        price="2.500000",
        currency="EUR",
        embedding=vector,
        active=active,
    )
    session.add(price)
    session.flush()
    return price


def test_postgres_migrations_and_vector_extension_present(postgres_session):
    tables = set(inspect(postgres_session.connection()).get_table_names())
    assert {
        "users",
        "projects",
        "price_items",
        "boq_rows",
        "mapping_decisions",
        "alembic_version",
    } <= tables
    versions = (
        postgres_session.execute(text("SELECT version_num FROM alembic_version"))
        .scalars()
        .all()
    )
    assert versions, (
        "Apply alembic upgrade head before running PostgreSQL integration tests"
    )
    assert (
        postgres_session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
        == "vector"
    )


def test_pgvector_cosine_ranking_excludes_other_owners_archived_and_missing_vectors(
    postgres_session,
):
    own, other = add_owner(postgres_session), add_owner(postgres_session)
    best = add_price(postgres_session, own, "OWN-BEST", [0.98, 0.02, 0.0])
    next_best = add_price(postgres_session, own, "OWN-NEXT", [0.7, 0.3, 0.0])
    distant = add_price(postgres_session, own, "OWN-DISTANT", [0.0, 1.0, 0.0])
    foreign = add_price(postgres_session, other, "FOREIGN-PERFECT", [1.0, 0.0, 0.0])
    archived = add_price(
        postgres_session, own, "ARCHIVED-PERFECT", [1.0, 0.0, 0.0], active=False
    )
    missing = add_price(postgres_session, own, "NO-VECTOR", None)
    results = semantic_candidates(postgres_session, own.id, [1.0, 0.0, 0.0], limit=20)
    assert [result["id"] for result in results] == [best.id, next_best.id, distant.id]
    assert foreign.id not in {result["id"] for result in results}
    assert archived.id not in {result["id"] for result in results}
    assert missing.id not in {result["id"] for result in results}
    assert (
        results[0]["similarity"] > results[1]["similarity"] > results[2]["similarity"]
    )
    assert results[0]["similarity"] == pytest.approx(0.99979, abs=0.0001)


def test_pgvector_roundtrip_and_limit(postgres_session):
    own = add_owner(postgres_session)
    first = add_price(postgres_session, own, "VECTOR-A", [0.25, 0.5, 0.75])
    add_price(postgres_session, own, "VECTOR-B", [0.75, 0.5, 0.25])
    postgres_session.expire(first)
    assert list(first.embedding) == pytest.approx([0.25, 0.5, 0.75])
    result = semantic_candidates(postgres_session, own.id, [0.25, 0.5, 0.75], limit=1)
    assert len(result) == 1
    assert result[0]["id"] == first.id
    assert result[0]["similarity"] == pytest.approx(1, abs=0.0001)


@pytest.mark.asyncio
async def test_embedding_http_contract_sorts_provider_vectors(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-placeholder"
        assert payload == {
            "model": "multilingual-test",
            "input": ["Strukturë FV", "Montim fotovoltaik"],
        }
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.2, 0.8]},
                    {"index": 0, "embedding": [0.9, 0.1]},
                ]
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    config = MatchingConfig(
        base_url="https://ai.example/v1",
        api_key="test-placeholder",
        embedding_model="multilingual-test",
    )
    assert await embed_texts(["Strukturë FV", "Montim fotovoltaik"], config) == [
        [0.9, 0.1],
        [0.2, 0.8],
    ]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_embedding_rejects_malformed_provider_vectors(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.9, 0.1]},
                    {"index": 1, "embedding": [0.8]},
                ]
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    config = MatchingConfig(
        base_url="https://ai.example/v1",
        api_key="test-placeholder",
        embedding_model="multilingual-test",
    )
    with pytest.raises(ValueError, match="Invalid embeddings"):
        await embed_texts(["first", "second"], config)


@pytest.mark.asyncio
async def test_ai_request_omits_private_project_quantity_and_price_data(monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        body = request.content.decode()
        assert "SECRET-CLIENT-NAME" not in body
        assert "PRIVATE-NOTE" not in body
        assert "987654321" not in body
        assert "123456789" not in body
        supplied = json.loads(json.loads(body)["messages"][1]["content"])
        assert set(supplied["boq"]) == {"description", "unit"}
        assert set(supplied["candidates"][0]) <= {
            "id",
            "code",
            "name",
            "description",
            "unit",
            "technical_specs",
            "price_kind",
            "supply_included",
            "installation_included",
            "transport_included",
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "candidate_id": 1,
                                    "confidence": 0.85,
                                    "compatible": True,
                                    "explanation": "Kontrolloni specifikimet.",
                                    "discrepancies": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    config = MatchingConfig(
        base_url="https://ai.example/v1",
        api_key="test-placeholder",
        ai_model="compare-test",
    )
    result = await compare_with_ai(
        {
            "description": "Montim strukturë FV",
            "unit": "kg",
            "client": "SECRET-CLIENT-NAME",
            "quantity": "987654321",
        },
        [
            {
                "id": 1,
                "description": "Montim konstruksion FV",
                "unit": "kg",
                "notes": "PRIVATE-NOTE",
                "price": "123456789",
            }
        ],
        config,
    )
    assert result["candidate_id"] == 1


@pytest.mark.asyncio
async def test_embed_text_requires_configuration():
    with pytest.raises(ValueError, match="not configured"):
        await embed_text("Montim", MatchingConfig())
