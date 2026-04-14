def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_delete_user_self_or_root(client, create_user, root_token):
    user = create_user("eve", "eve@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": "eve", "password": "password123"},
    )
    user_token = login_response.json()["access_token"]

    response = client.delete(
        f"/users/{user.id}",
        headers=auth_headers(user_token),
    )
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    another_user = create_user("eve2", "eve2@example.com", "password123")
    root_delete_response = client.delete(
        f"/users/{another_user.id}",
        headers=auth_headers(root_token),
    )
    assert root_delete_response.status_code == 200
    assert "deleted successfully" in root_delete_response.json()["message"]


def test_get_user_information(client, auth_token, create_user):
    user = create_user("frank", "frank@example.com", "password123")
    response = client.get(
        f"/users/{user.id}",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["username"] == "frank"


def test_update_user_information(client, root_token, create_user):
    user = create_user("gina", "gina@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": "gina", "password": "password123"},
    )
    gina_token = login_response.json()["access_token"]

    update_response = client.put(
        f"/users/{user.id}",
        json={"username": "gina_updated", "password": "newpassword123"},
        headers=auth_headers(gina_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["username"] == "gina_updated"

    root_update_response = client.put(
        f"/users/{user.id}",
        json={"username": "gina_root", "password": "newpassword123"},
        headers=auth_headers(root_token),
    )
    assert root_update_response.status_code == 200
