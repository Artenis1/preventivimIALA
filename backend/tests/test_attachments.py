from app.config import get_settings


def test_price_attachment_download_and_path_safety(
    client, price, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path / "uploads"))
    payload = b"%PDF-1.4\nDummy engineering document\n%%EOF"
    response = client.post(
        f"/api/prices/{price['id']}/attachments",
        files={"file": ("../../supplier-quote.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert attachment["filename"] == "supplier-quote.pdf"
    assert attachment["size"] == len(payload)
    assert len(attachment["id"]) == 32
    assert (tmp_path / "uploads" / attachment["id"]).read_bytes() == payload
    assert not (tmp_path / "supplier-quote.pdf").exists()
    response = client.get(f"/api/prices/{price['id']}/attachments/{attachment['id']}")
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment;")
    # Another user cannot read source documents or attach to the private price.
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/register",
        json={
            "email": "attachment-other@example.com",
            "password": "attachment-other-password",
        },
    )
    assert (
        client.get(
            f"/api/prices/{price['id']}/attachments/{attachment['id']}"
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/prices/{price['id']}/attachments",
            files={"file": ("x.pdf", payload, "application/pdf")},
        ).status_code
        == 404
    )


def test_attachment_validation_and_size_limit(client, price, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path / "uploads"))
    endpoint = f"/api/prices/{price['id']}/attachments"
    for name, payload in [
        ("x.html", b"<script>bad</script>"),
        ("x.pdf", b"not pdf"),
        ("x.png", b"%PDF-1.4"),
    ]:
        response = client.post(
            endpoint, files={"file": (name, payload, "application/octet-stream")}
        )
        assert response.status_code == 422
    response = client.post(
        endpoint,
        files={
            "file": ("big.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf")
        },
    )
    assert response.status_code == 413
    assert not (tmp_path / "uploads").exists()
    assert client.get(f"{endpoint}/{'a' * 32}").status_code == 404


def test_price_attachment_count_limit(client, price, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path / "uploads"))
    endpoint = f"/api/prices/{price['id']}/attachments"
    for index in range(20):
        response = client.post(
            endpoint,
            files={
                "file": (f"quote-{index}.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")
            },
        )
        assert response.status_code == 201, response.text
    assert (
        client.post(
            endpoint,
            files={"file": ("one-too-many.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        ).status_code
        == 422
    )
    assert len(list((tmp_path / "uploads").iterdir())) == 20
