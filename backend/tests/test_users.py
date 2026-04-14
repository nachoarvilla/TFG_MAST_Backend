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


def test_delete_user_requires_auth(client, create_user):
    user = create_user("tom", "tom@example.com", "password123")
    response = client.delete(f"/users/{user.id}")
    assert response.status_code == 401


def test_delete_user_not_owner_or_root(client, auth_token, create_user):
    user = create_user("jack", "jack@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": user.username, "password": "password123"},
    )
    user_token = login_response.json()["access_token"]

    create_response = client.post(
        "/register",
        json={"username": "another", "email": "another@example.com", "password": "secret123"},
    )
    assert create_response.status_code == 201
    another_id = create_response.json()["id"]

    forbidden = client.delete(
        f"/users/{another_id}",
        headers=auth_headers(user_token),
    )
    assert forbidden.status_code == 403


def test_delete_user_not_found(client, auth_token):
    response = client.delete(
        "/users/9999",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404


def test_get_user_information(client, auth_token, create_user):
    user = create_user("frank", "frank@example.com", "password123")
    response = client.get(
        f"/users/{user.id}",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["username"] == "frank"


def test_get_user_information_requires_auth(client, create_user):
    user = create_user("anna", "anna@example.com", "password123")
    response = client.get(f"/users/{user.id}")
    assert response.status_code == 401


def test_get_user_not_found(client, auth_token):
    response = client.get(
        "/users/9999",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404


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


def test_update_user_requires_auth(client, create_user):
    user = create_user("ursula", "ursula@example.com", "password123")
    response = client.put(
        f"/users/{user.id}",
        json={"username": "ursula_new"},
    )
    assert response.status_code == 401


def test_update_user_not_owner_or_root(client, auth_token, create_user):
    user = create_user("peter", "peter@example.com", "password123")
    another = create_user("jane", "jane@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": another.username, "password": "password123"},
    )
    another_token = login_response.json()["access_token"]

    update_response = client.put(
        f"/users/{user.id}",
        json={"username": "newname"},
        headers=auth_headers(another_token),
    )
    assert update_response.status_code == 403


def test_update_user_username_conflict(client, auth_token, create_user):
    existing_user = create_user("existing", "existing@example.com", "password123")
    user = create_user("conflict", "conflict@example.com", "password123")
    
    # Login as the conflict user to update their profile
    login_response = client.post(
        "/login",
        json={"username_or_email": user.username, "password": "password123"},
    )
    user_token = login_response.json()["access_token"]
    
    update_response = client.put(
        f"/users/{user.id}",
        json={"username": existing_user.username},
        headers=auth_headers(user_token),
    )
    assert update_response.status_code == 400
    assert "already taken" in update_response.json()["detail"]
