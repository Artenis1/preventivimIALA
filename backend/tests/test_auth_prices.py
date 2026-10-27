def test_auth_session_login_logout(client):
    assert client.get("/api/prices").status_code == 401
    result = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "long-password-123",
            "display_name": "Test",
        },
    )
    assert result.status_code == 201
    assert "HttpOnly" in result.headers["set-cookie"]
    assert client.get("/api/auth/me").json()["display_name"] == "Test"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong-password-123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "long-password-123"},
        ).status_code
        == 200
    )


def test_duplicate_and_history(client, price):
    body = {
        k: price[k]
        for k in ("code", "name", "description", "unit", "price", "currency")
    }
    assert client.post("/api/prices", json=body).status_code == 409
    body["price"] = "120.12"
    body["reason"] = "Ofertë e re"
    assert client.put(f"/api/prices/{price['id']}", json=body).status_code == 200
    history = client.get("/api/prices/history").json()
    assert history[0]["old_price"] == "100.000000"
    assert history[0]["new_price"] == "120.120000"
    assert client.delete(f"/api/prices/{price['id']}").status_code == 204
    assert client.get("/api/prices").json() == []


def test_private_prices(client, price):
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "another-password-123"},
    )
    assert client.get("/api/prices").json() == []
    assert client.delete(f"/api/prices/{price['id']}").status_code == 404


def test_origin_and_validation(client, user):
    assert (
        client.post(
            "/api/prices", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/prices",
            json={
                "code": "X",
                "name": "X",
                "description": "X",
                "unit": "m",
                "price": "NaN",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/prices",
            json={
                "code": "X",
                "name": "X",
                "description": "X",
                "unit": "m",
                "price": "1",
                "valid_until": "bad-date",
            },
        ).status_code
        == 422
    )


def test_codes_case_insensitive(client, price):
    body = {k: price[k] for k in ("code", "name", "description", "unit", "price", "currency")}
    body["code"] = price["code"].lower()
    assert client.post("/api/prices", json=body).status_code == 409
