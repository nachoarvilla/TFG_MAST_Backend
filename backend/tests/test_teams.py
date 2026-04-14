def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_create_team_requires_auth(client):
    response = client.post(
        "/teams",
        json={"name": "Team A", "description": "Test team"},
    )
    assert response.status_code == 401


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

    remove_response = client.request(
        "DELETE",
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


def test_update_team_information(client, auth_token):
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
