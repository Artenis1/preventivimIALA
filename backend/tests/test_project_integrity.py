"""Quote snapshots and explicit human decisions survive unrelated changes."""

from decimal import Decimal

from test_project_workflow import create_project, upload_boq


def change_price(client, item, **changes):
    fields = (
        "code",
        "name",
        "description",
        "unit",
        "price",
        "currency",
        "supply_included",
        "installation_included",
        "vat_included",
        "vat_rate",
    )
    value = {k: item[k] for k in fields}
    value.update(changes)
    response = client.put(f"/api/prices/{item['id']}", json=value)
    assert response.status_code == 200, response.text
    return response.json()


def approved_row(client, price):
    project = create_project(client)
    imported, _ = upload_boq(client, project)
    row = imported["rows"][0]
    url = f"/api/projects/{project['id']}/rows/{row['id']}"
    response = client.patch(
        url,
        json={
            "item_id": price["id"],
            "decision": "approved",
            "unit_price": "125",
            "notes": "Quote A",
        },
    )
    assert response.status_code == 200, response.text
    return project, url, response.json()


def test_editing_approved_quote_does_not_refresh_catalog_price(client, price):
    project, url, original = approved_row(client, price)
    change_price(client, price, price="200")
    response = client.patch(
        url,
        json={
            "decision": "approved",
            "notes": "Quote reviewed",
            "confirm_override": True,
        },
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert Decimal(changed["unit_price"]) == Decimal("125")
    assert Decimal(changed["original_unit_price"]) == Decimal("100")
    assert changed["price_snapshot"] == original["price_snapshot"]
    assert changed["notes"] == "Quote reviewed"
    response = client.patch(url, json={"unit_price": "130", "confirm_override": True})
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["decision"] == "approved"
    assert Decimal(changed["unit_price"]) == Decimal("130")
    assert Decimal(changed["original_unit_price"]) == Decimal("100")
    assert changed["price_snapshot"] == original["price_snapshot"]
    assert changed["notes"] == "Quote reviewed"


def test_explicit_manual_price_clears_suggested_catalog_item(client, price):
    project = create_project(client)
    pid = project["id"]
    imported, _ = upload_boq(client, project)
    client.post(f"/api/projects/{pid}/match")
    row = imported["rows"][0]
    url = f"/api/projects/{pid}/rows/{row['id']}"
    response = client.patch(
        url, json={"item_id": None, "decision": "approved", "unit_price": "77"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["item_id"] is None
    assert response.json()["price_snapshot"]["manual"] is True
    # Notes-only edits preserve manual quotes even if a previous AI suggestion exists.
    response = client.patch(
        url, json={"notes": "Manual quote retained", "confirm_override": True}
    )
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "approved"
    assert response.json()["item_id"] is None
    assert Decimal(response.json()["unit_price"]) == 77


def test_converted_quote_price_has_stable_persistence_precision(client, price):
    change_price(client, price, price="1", vat_included=True, vat_rate="20")
    project = create_project(client)
    pid = project["id"]
    imported, _ = upload_boq(client, project, quantity="1000000")
    row = imported["rows"][0]
    response = client.patch(
        f"/api/projects/{pid}/rows/{row['id']}",
        json={"item_id": price["id"], "decision": "approved"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result["unit_price"]) == Decimal("0.833333")
    assert Decimal(result["price_snapshot"]["unit_price"]) == Decimal(
        result["unit_price"]
    )
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["rows"][0]["total"] == "833333.00"
    assert Decimal(detail["rows"][0]["original_unit_price"]) == Decimal(
        result["unit_price"]
    )


def test_bulk_approval_rechecks_item_version_even_when_price_unchanged(client, price):
    project = create_project(client)
    pid = project["id"]
    imported, _ = upload_boq(client, project)
    row = imported["rows"][0]
    response = client.post(f"/api/projects/{pid}/match")
    assert response.status_code == 200, response.text
    assert len(client.get(f"/api/projects/{pid}/approve-preview").json()["rows"]) == 1
    change_price(client, price, description="Furnizim beton C40/50")
    assert client.get(f"/api/projects/{pid}/approve-preview").json()["rows"] == []
    assert (
        client.post(
            f"/api/projects/{pid}/approve-bulk",
            json={"confirm": True, "row_ids": [row["id"]]},
        ).status_code
        == 409
    )


def test_finalized_snapshot_metadata_and_immutability(client, price):
    project, url, row = approved_row(client, price)
    pid = project["id"]
    assert (
        client.post(f"/api/projects/{pid}/finalize", json={"confirm": True}).status_code
        == 200
    )
    detail = client.get(f"/api/projects/{pid}").json()
    version = detail["versions"][0]["snapshot"]
    assert version["status"] == "finalized"
    assert version["project"]["status"] == "finalized"
    assert (
        client.patch(
            url, json={"notes": "Forbidden", "confirm_override": True}
        ).status_code
        == 409
    )
    change_price(client, price, price="999")
    assert (
        client.get(f"/api/projects/{pid}").json()["versions"][0]["snapshot"] == version
    )


def test_version_comparison_includes_line_changes(client, price):
    project, url, row = approved_row(client, price)
    pid = project["id"]
    assert (
        client.post(f"/api/projects/{pid}/finalize", json={"confirm": True}).status_code
        == 200
    )
    assert (
        client.post(f"/api/projects/{pid}/reopen", json={"confirm": True}).status_code
        == 200
    )
    assert (
        client.patch(
            url, json={"unit_price": "130", "confirm_override": True}
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/projects/{pid}/finalize", json={"confirm": True}).status_code
        == 200
    )
    response = client.get(f"/api/projects/{pid}/compare?left=1&right=2")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["currency"] == "EUR"
    assert result["comparable_currency"] is True
    assert result["changed_row_count"] == 1
    difference = result["row_differences"][0]
    assert difference["row_id"] == row["id"]
    assert difference["change"] == "changed"
    assert Decimal(difference["unit_price_difference"]) == 5
    assert Decimal(difference["total_difference"]) == 10
    assert difference["old_unit"] == difference["new_unit"] == "m³"


def test_comparison_does_not_subtract_different_currencies(client, price):
    project, url, row = approved_row(client, price)
    pid = project["id"]
    client.post(f"/api/projects/{pid}/finalize", json={"confirm": True})
    client.post(f"/api/projects/{pid}/reopen", json={"confirm": True})
    client.patch(url, json={"decision": "pending", "confirm_override": True})
    assert (
        client.patch(
            f"/api/projects/{pid}", json={"name": "Parku FV", "currency": "ALL"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            url, json={"item_id": None, "decision": "approved", "unit_price": "130"}
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/projects/{pid}/finalize", json={"confirm": True}).status_code
        == 200
    )
    result = client.get(f"/api/projects/{pid}/compare?left=1&right=2").json()
    assert result["comparable_currency"] is False
    assert result["left_currency"] == "EUR"
    assert result["right_currency"] == "ALL"
    assert result["grand_total_difference"] is None
    assert result["row_differences"][0]["unit_price_difference"] is None
    assert result["warnings"]


def test_import_refuses_silent_decimal_precision_loss(client, user):
    from io import BytesIO
    from openpyxl import Workbook

    project = create_project(client)
    pid = project["id"]
    for quantity, unit_price, total in [
        ("1.1234567", 1, 1),
        (1, "1.1234567", 1),
        (1, 1, "1.1234567"),
        (1, -1, 1),
        (1, 1, -1),
    ]:
        wb = Workbook()
        ws = wb.active
        ws.append(["Nr", "Kodi", "Përshkrimi", "Njësia", "Sasia", "Çmimi", "Vlera"])
        ws.append(["1", "C", "Punim", "m", quantity, unit_price, total])
        stream = BytesIO()
        wb.save(stream)
        response = client.post(
            f"/api/projects/{pid}/imports",
            files={"file": ("precision.xlsx", stream.getvalue())},
        )
        assert response.status_code == 200, response.text
        upload = response.json()
        sheet = upload["sheets"][0]
        response = client.post(
            f"/api/projects/{pid}/imports/{upload['upload_id']}/commit",
            json={
                "sheet": sheet["name"],
                "header_row": sheet["header_row"],
                "mapping": sheet["suggested_mapping"],
            },
        )
        assert response.status_code == 422, response.text
    assert client.get(f"/api/projects/{pid}").json()["rows"] == []
