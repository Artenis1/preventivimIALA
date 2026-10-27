import httpx
import pytest
from app.services import matching


@pytest.fixture
def item():
    return {
        "id": 1,
        "code": "PV-001",
        "name": "Montim panele FV",
        "description": "Montim i paneleve fotovoltaike",
        "unit": "copë",
        "price": "20.00",
        "currency": "EUR",
        "price_kind": "installed",
        "installation_included": True,
        "supply_included": False,
        "active": True,
    }


@pytest.mark.asyncio
async def test_exact_code_and_normalization(item):
    result = await matching.match_row(
        {"code": "PV-001", "description": "Montim panele FV", "unit": "pcs"}, [item]
    )
    assert result["suggested_item_id"] == 1
    assert result["method"] == "code"
    assert result["classification"] == "high"
    assert result["review_status"] == "suggested"  # never approved by AI
    result = await matching.match_row(
        {"description": " MONTIM, i paneleve FOTOVOLTAIKE! ", "unit": "copë"}, [item]
    )
    assert result["method"] == "normalized"


@pytest.mark.asyncio
async def test_supply_and_installation_difference_is_reviewed_even_with_exact_code(
    item,
):
    result = await matching.match_row(
        {
            "code": "PV-001",
            "description": "Furnizim dhe montim panele FV",
            "unit": "copë",
        },
        [item],
    )
    assert result["classification"] == "medium"
    assert any("supply" in problem for problem in result["discrepancies"])


@pytest.mark.asyncio
async def test_different_concrete_grade_not_automatic():
    item = {
        "id": 2,
        "code": "BET",
        "description": "Beton C20/25",
        "unit": "m3",
        "price": "100",
    }
    result = await matching.match_row(
        {"code": "BET", "description": "Beton C30/37", "unit": "m3"}, [item]
    )
    assert result["classification"] != "high"
    assert any("grade" in issue for issue in result["discrepancies"])


@pytest.mark.asyncio
async def test_incompatible_units_not_automatic(item):
    result = await matching.match_row(
        {"code": item["code"], "description": item["description"], "unit": "m2"}, [item]
    )
    assert result["unit_compatible"] is False
    assert result["classification"] != "high"
    assert result["price_factor"] is None


@pytest.mark.asyncio
async def test_missing_unknown_description_has_no_price(item):
    result = await matching.match_row(
        {"description": "Asfalt rrugor", "unit": "m2"}, [item]
    )
    assert result["classification"] == "no_match"
    assert result["suggested_unit_price"] is None


@pytest.mark.asyncio
async def test_semantic_matching_with_different_words(monkeypatch):
    async def vectors(texts, config):
        assert len(texts) == 3
        return [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]

    monkeypatch.setattr(matching, "embed_texts", vectors)
    items = [
        {
            "id": 1,
            "code": "S1",
            "description": "Konstruksion metalik",
            "unit": "kg",
            "price": "4",
        },
        {
            "id": 2,
            "code": "T1",
            "description": "Germim dheu",
            "unit": "m3",
            "price": "8",
        },
    ]
    result = await matching.match_row(
        {"description": "Struktura mbajtëse", "unit": "kg"},
        items,
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "embedding_model": "multilingual",
        },
    )
    assert result["suggested_item_id"] == 1
    assert result["method"] == "semantic"
    assert result["confidence"] >= 0.92


@pytest.mark.asyncio
async def test_provider_failure_preserves_exact_matching(monkeypatch, item):
    async def failure(*args):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr(matching, "compare_with_ai", failure)
    result = await matching.match_row(
        {"code": item["code"], "description": item["description"], "unit": "pcs"},
        [item],
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "ai_model": "compare",
        },
    )
    assert result["suggested_item_id"] == item["id"]
    assert result["method"] == "code"
    assert result["ai_unavailable"] is True


@pytest.mark.asyncio
async def test_embedding_failure_keeps_keyword_search(monkeypatch):
    async def failure(*args):
        raise httpx.ReadTimeout("provider unavailable")

    monkeypatch.setattr(matching, "embed_texts", failure)
    result = await matching.match_row(
        {"description": "struktura mbajtëse FV", "unit": "kg"},
        [
            {
                "id": 1,
                "code": "S1",
                "description": "Konstruksion mbajtes fotovoltaik",
                "unit": "kg",
                "price": "4",
            }
        ],
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "embedding_model": "multilingual",
        },
    )
    assert result["suggested_item_id"] == 1
    assert result["method"] == "keywords"
    assert result["ai_unavailable"] is True


@pytest.mark.asyncio
async def test_ai_cannot_override_capacity_discrepancy(monkeypatch):
    async def compare(*args):
        return {
            "candidate_id": 1,
            "confidence": 0.999,
            "compatible": True,
            "explanation": "Equivalent",
            "discrepancies": [],
        }

    monkeypatch.setattr(matching, "compare_with_ai", compare)
    result = await matching.match_row(
        {"code": "INV", "description": "Inverter 50 kW", "unit": "piece"},
        [
            {
                "id": 1,
                "code": "INV",
                "description": "Inverter 100 kW",
                "unit": "piece",
                "price": "100",
            }
        ],
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "ai_model": "compare",
        },
    )
    assert result["classification"] != "high"
    assert any("power" in problem for problem in result["discrepancies"])


@pytest.mark.asyncio
async def test_rejected_mapping_excludes_candidate(item):
    row = {"description": "Montim panele FV", "unit": "piece"}
    result = await matching.match_row(
        row,
        [item],
        [{"description": row["description"], "item_id": 1, "decision": "rejected"}],
    )
    assert result["suggested_item_id"] is None


@pytest.mark.asyncio
async def test_learning_mapping_reuses_approval_but_checks_units(item):
    row = {"description": "Punim sipas zërit 23", "unit": "m"}
    result = await matching.match_row(
        row,
        [item],
        [
            {
                "normalized_description": "punim sipas zerit 23",
                "item_id": 1,
                "decision": "approved",
            }
        ],
    )
    assert result["method"] == "approved_mapping"
    assert result["classification"] != "high"


def test_pgvector_query_scopes_user_and_parameters():
    sql = matching.pgvector_nearest_sql()
    assert "owner_id = :owner_id" in sql
    assert "<=>" in sql
    assert ":embedding" in sql
    with pytest.raises(ValueError):
        matching.pgvector_nearest_sql("price_items; DROP TABLE users")


@pytest.mark.asyncio
async def test_model_boolean_decisions_latest_approval_wins(item):
    row = {"description": "Punim specifik", "unit": "piece"}
    decisions = [
        {
            "id": 1,
            "normalized_description": "punim specifik",
            "item_id": 1,
            "approved": False,
        },
        {
            "id": 2,
            "normalized_description": "punim specifik",
            "item_id": 1,
            "approved": True,
        },
    ]
    result = await matching.match_row(row, [item], decisions)
    assert result["suggested_item_id"] == 1
    assert result["method"] == "approved_mapping"


@pytest.mark.asyncio
async def test_persisted_embeddings_only_request_query_vector(monkeypatch):
    async def vectors(texts, config):
        assert texts == ["Struktura mbajtëse"]
        return [[1.0, 0.0]]

    monkeypatch.setattr(matching, "embed_texts", vectors)
    items = [
        {
            "id": 1,
            "description": "Konstruksion metalik",
            "unit": "kg",
            "price": "4",
            "_embedding": [1.0, 0.01],
        },
        {
            "id": 2,
            "description": "Germim dheu",
            "unit": "m3",
            "price": "8",
            "_embedding": [0.0, 1.0],
        },
    ]
    result = await matching.match_row(
        {"description": "Struktura mbajtëse", "unit": "kg"},
        items,
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "embedding_model": "multilingual",
        },
    )
    assert result["suggested_item_id"] == 1
    assert result["method"] == "semantic"


@pytest.mark.asyncio
async def test_pgvector_scores_do_not_request_embeddings(monkeypatch):
    async def no_calls(*args):
        raise AssertionError("Persisted pgvector scores require no provider calls")

    monkeypatch.setattr(matching, "embed_texts", no_calls)
    items = [
        {
            "id": 1,
            "description": "Konstruksion metalik",
            "unit": "kg",
            "price": "4",
            "_semantic_similarity": 0.97,
        }
    ]
    result = await matching.match_row(
        {"description": "Struktura mbajtëse", "unit": "kg"},
        items,
        config={
            "base_url": "https://ai.example/v1",
            "api_key": "test",
            "embedding_model": "multilingual",
        },
    )
    assert result["suggested_item_id"] == 1
    assert result["method"] == "semantic"


@pytest.mark.asyncio
async def test_learned_mapping_filters_incompatible_mapping_unit(item):
    row = {"description": "Punim specifik", "unit": "piece"}
    decisions = [
        {
            "normalized_description": "punim specifik",
            "item_id": 1,
            "approved": True,
            "unit": "m2",
        }
    ]
    result = await matching.match_row(row, [item], decisions)
    assert result["method"] != "approved_mapping"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested,stored",
    [
        ("Profil metalik 100x50x3 mm", "Profil metalik 100x50x5 mm"),
        ("Armature Ø12 mm", "Armature Ø16 mm"),
        ("Tulle tipi 32", "Tulle tipi 25"),
    ],
)
async def test_dimension_and_unclassified_numeric_specifications_force_review(
    requested, stored
):
    result = await matching.match_row(
        {"code": "X1", "description": requested, "unit": "kg"},
        [{"id": 1, "code": "X1", "description": stored, "unit": "kg", "price": "5"}],
    )
    assert result["classification"] != "high"
    assert result["discrepancies"]


@pytest.mark.asyncio
async def test_equivalent_power_specifications_are_compatible():
    result = await matching.match_row(
        {"code": "X1", "description": "Inverter 1000 W", "unit": "piece"},
        [
            {
                "id": 1,
                "code": "X1",
                "description": "Inverter 1 kW",
                "unit": "piece",
                "price": "5",
            }
        ],
    )
    assert result["classification"] == "high"
    assert not result["discrepancies"]


@pytest.mark.asyncio
async def test_duplicate_normalized_descriptions_require_review_even_with_one_candidate_limit():
    candidates = [
        {"id": 1, "code": "A1", "description": "Montim panelesh FV", "unit": "piece", "price": "10"},
        {"id": 2, "code": "B1", "description": "MONTIM, panelesh FV!", "unit": "piece", "price": "20"},
    ]
    result = await matching.match_row(
        {"description": "Montim panelesh FV", "unit": "piece"}, candidates,
        config={"max_candidates": 1},
    )
    assert result["method"] == "normalized"
    assert result["classification"] == "medium"
    assert result["discrepancies"]


@pytest.mark.asyncio
async def test_duplicate_normalized_codes_require_review():
    candidates = [
        {"id": 1, "code": "PV-1", "description": "Montim panelesh FV", "unit": "piece", "price": "10"},
        {"id": 2, "code": "pv-1", "description": "Montim module FV", "unit": "piece", "price": "20"},
    ]
    result = await matching.match_row(
        {"code": "PV-1", "description": "Montim FV", "unit": "piece"}, candidates,
    )
    assert result["method"] == "code"
    assert result["classification"] == "medium"
    assert result["discrepancies"]


@pytest.mark.asyncio
async def test_conflicting_approved_mappings_require_review():
    candidates = [
        {"id": 1, "code": "A1", "description": "Montim panelesh FV", "unit": "piece", "price": "10"},
        {"id": 2, "code": "B1", "description": "Montim module FV", "unit": "piece", "price": "20"},
    ]
    decisions = [
        {"id": 1, "normalized_description": "punim i zgjedhur", "unit": "piece", "item_id": 1, "approved": True},
        {"id": 2, "normalized_description": "punim i zgjedhur", "unit": "piece", "item_id": 2, "approved": True},
    ]
    result = await matching.match_row(
        {"description": "Punim i zgjedhur", "unit": "piece"}, candidates, decisions,
    )
    assert result["method"] == "approved_mapping"
    assert result["classification"] == "medium"
    assert result["discrepancies"]


@pytest.mark.asyncio
async def test_unique_exact_code_disambiguates_duplicate_descriptions():
    candidates = [
        {"id": 1, "code": "A1", "description": "Montim panelesh FV", "unit": "piece", "price": "10"},
        {"id": 2, "code": "B1", "description": "Montim panelesh FV", "unit": "piece", "price": "20"},
    ]
    result = await matching.match_row(
        {"code": "B1", "description": "Montim panelesh FV", "unit": "piece"}, candidates,
    )
    assert result["suggested_item_id"] == 2
    assert result["method"] == "code"
    assert result["classification"] == "high"


@pytest.mark.asyncio
async def test_valid_low_medium_setting_infers_compatible_low_threshold(item):
    result = await matching.match_row(
        {"code": item["code"], "description": item["description"], "unit": "piece"},
        [item], config={"medium_confidence": 0.2},
    )
    assert result["classification"] == "high"
    assert matching.MatchingConfig(medium_threshold=0.2).low_threshold == 0.2


def test_environment_low_threshold_inference_and_explicit_override(monkeypatch):
    monkeypatch.setenv("MATCH_MEDIUM_THRESHOLD", "0.2")
    monkeypatch.delenv("MATCH_LOW_THRESHOLD", raising=False)
    assert matching.MatchingConfig.from_env().low_threshold == 0.2
    monkeypatch.setenv("MATCH_LOW_THRESHOLD", "0.1")
    assert matching.MatchingConfig.from_env().low_threshold == 0.1
