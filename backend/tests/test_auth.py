def test_root_and_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to the MAST backend"

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["api"] == "running"


def test_register_and_login(client):
    response = client.post(
        "/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    assert response.json()["username"] == "alice"

    response = client.post(
        "/login",
        json={"username_or_email": "alice", "password": "secret123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
