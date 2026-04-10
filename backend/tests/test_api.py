import pytest


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


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


def test_create_team_requires_auth(client):
    response = client.post(
        "/teams",
        json={"name": "Team A", "description": "Test team"},
    )
    assert response.status_code == 403


def test_create_team_success(client, auth_token):
    response = client.post(
        "/teams",
        json={"name": "Team A", "description": "A sample team"},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Team A"
    assert payload["description"] == "A sample team"
    assert "id" in payload


def test_add_team_member_by_leader(client, auth_token, create_user):
    new_member = create_user("bob", "bob@example.com", "password123")

    create_response = client.post(
        "/teams",
        json={"name": "Team B", "description": "Team for tests"},
        headers=auth_headers(auth_token),
    )
    assert create_response.status_code == 201
    team_id = create_response.json()["id"]

    add_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": new_member.username},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 201
    assert "added to team" in add_response.json()["message"]


def test_remove_team_member_by_leader(client, auth_token, create_user):
    member = create_user("carol", "carol@example.com", "password123")

    create_response = client.post(
        "/teams",
        json={"name": "Team C", "description": "Team remove test"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    add_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": member.username},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 201

    remove_response = client.delete(
        f"/teams/{team_id}/members",
        json={"username": member.username},
        headers=auth_headers(auth_token),
    )
    assert remove_response.status_code == 200
    assert "removed from team" in remove_response.json()["message"]


def test_list_team_members_by_member(client, auth_token, create_user):
    member = create_user("dan", "dan@example.com", "password123")

    create_response = client.post(
        "/teams",
        json={"name": "Team D", "description": "Team member list"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    add_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": member.username},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 201

    login_response = client.post(
        "/login",
        json={"username_or_email": member.username, "password": "password123"},
    )
    member_token = login_response.json()["access_token"]

    list_response = client.get(
        f"/teams/{team_id}/members",
        headers=auth_headers(member_token),
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["team_id"] == team_id
    assert any(item["username"] == member.username for item in payload["members"])


def test_create_project_and_get_by_owner(client, auth_token):
    create_response = client.post(
        "/projects",
        json={"name": "Project X", "description": "A test project", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    get_response = client.get(
        f"/projects/{project_id}",
        headers=auth_headers(auth_token),
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Project X"
    assert get_response.json()["user_role"] == "owner"


def test_update_project_by_owner(client, auth_token):
    create_response = client.post(
        "/projects",
        json={"name": "Project Y", "description": "Update test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    update_response = client.put(
        f"/projects/{project_id}",
        json={"name": "Project Y Updated", "description": "Updated description", "is_private": False},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Project Y Updated"
    assert update_response.json()["is_private"] is False


def test_delete_project_by_owner(client, auth_token):
    create_response = client.post(
        "/projects",
        json={"name": "Project Z", "description": "Delete test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/projects/{project_id}",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"]


@pytest.mark.xfail(reason="Endpoint not implemented yet")
def test_delete_user_self_or_root(client, auth_token, root_token, create_user):
    user = create_user("eve", "eve@example.com", "password123")
    response = client.delete(
        f"/users/{user.id}",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200

    root_delete_response = client.delete(
        f"/users/{user.id}",
        headers=auth_headers(root_token),
    )
    assert root_delete_response.status_code == 200


@pytest.mark.xfail(reason="Endpoint not implemented yet")
def test_get_user_information(client, auth_token, create_user):
    user = create_user("frank", "frank@example.com", "password123")
    response = client.get(
        f"/users/{user.id}",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["username"] == "frank"


@pytest.mark.xfail(reason="Endpoint not implemented yet")
def test_update_user_information(client, auth_token, root_token, create_user):
    user = create_user("gina", "gina@example.com", "password123")
    update_response = client.put(
        f"/users/{user.id}",
        json={"username": "gina_updated", "password": "newpassword123"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["username"] == "gina_updated"

    root_update_response = client.put(
        f"/users/{user.id}",
        json={"username": "gina_root", "password": "newpassword123"},
        headers=auth_headers(root_token),
    )
    assert root_update_response.status_code == 200


@pytest.mark.xfail(reason="Endpoint not implemented yet")
def test_get_team_information(client, auth_token, create_user):
    member = create_user("henry", "henry@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team E", "description": "Info test"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]
    client.post(
        f"/teams/{team_id}/members",
        json={"username": member.username},
        headers=auth_headers(auth_token),
    )
    login_response = client.post(
        "/login",
        json={"username_or_email": member.username, "password": "password123"},
    )
    member_token = login_response.json()["access_token"]

    response = client.get(
        f"/teams/{team_id}",
        headers=auth_headers(member_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Team E"
    assert any(item["username"] == member.username for item in response.json()["members"])


@pytest.mark.xfail(reason="Endpoint not implemented yet")
def test_update_team_information(client, auth_token, create_user):
    create_response = client.post(
        "/teams",
        json={"name": "Team F", "description": "Update info"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    update_response = client.put(
        f"/teams/{team_id}",
        json={"name": "Team F Updated", "description": "Updated description"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Team F Updated"
