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


def test_create_team_duplicate_name(client, auth_token):
    client.post(
        "/teams",
        json={"name": "Team A", "description": "First team"},
        headers=auth_headers(auth_token),
    )
    duplicate_response = client.post(
        "/teams",
        json={"name": "Team A", "description": "Duplicate name"},
        headers=auth_headers(auth_token),
    )
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"]


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


def test_add_team_member_requires_leader(client, auth_token, create_user):
    other_user = create_user("noleader", "noleader@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team G", "description": "No leader add test"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    other_token = login_response.json()["access_token"]

    add_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": "bob"},
        headers=auth_headers(other_token),
    )
    assert add_response.status_code == 403


def test_add_team_member_team_not_found(client, auth_token):
    response = client.post(
        "/teams/9999/members",
        json={"username": "doesnotmatter"},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Team not found"


def test_add_team_member_user_not_found(client, auth_token):
    create_response = client.post(
        "/teams",
        json={"name": "Team H", "description": "Add unknown user"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    add_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": "unknown_user"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 404
    assert add_response.json()["detail"] == "User not found"


def test_remove_team_member_requires_leader(client, auth_token, create_user):
    member = create_user("carol2", "carol2@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team I", "description": "Remove require leader"},
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

    remove_response = client.request(
        "DELETE",
        f"/teams/{team_id}/members",
        json={"username": member.username},
        headers=auth_headers(member_token),
    )
    assert remove_response.status_code == 403


def test_remove_team_member_not_a_member(client, auth_token):
    create_response = client.post(
        "/teams",
        json={"name": "Team J", "description": "Remove not member"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    remove_response = client.request(
        "DELETE",
        f"/teams/{team_id}/members",
        json={"username": "ghost"},
        headers=auth_headers(auth_token),
    )
    assert remove_response.status_code == 404
    assert remove_response.json()["detail"] == "User not found"


def test_delete_team_by_non_leader(client, auth_token, create_user):
    member = create_user("mike", "mike@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team K", "description": "Delete non-leader"},
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

    delete_response = client.delete(
        f"/teams/{team_id}",
        headers=auth_headers(member_token),
    )
    assert delete_response.status_code == 403
    assert "Only the team leader" in delete_response.json()["detail"]


def test_delete_team_by_leader_success(client, auth_token):
    create_response = client.post(
        "/teams",
        json={"name": "Team Q", "description": "Leader delete success"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/teams/{team_id}",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"]


def test_delete_team_not_found(client, auth_token):
    response = client.delete(
        "/teams/9999",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Team not found"


def test_get_team_information_requires_auth(client):
    response = client.get("/teams/1")
    assert response.status_code == 401


def test_get_team_information_non_member(client, auth_token, create_user):
    outsider = create_user("outsider", "outsider@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team L", "description": "Non-member view test"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    response = client.get(
        f"/teams/{team_id}",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403


def test_update_team_information_not_leader(client, auth_token, create_user):
    member = create_user("nina", "nina@example.com", "password123")
    create_response = client.post(
        "/teams",
        json={"name": "Team M", "description": "Update not leader"},
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

    update_response = client.put(
        f"/teams/{team_id}",
        json={"name": "Team M Updated", "description": "New desc"},
        headers=auth_headers(member_token),
    )
    assert update_response.status_code == 403


def test_update_team_information_duplicate_name(client, auth_token):
    client.post(
        "/teams",
        json={"name": "Team N", "description": "First team"},
        headers=auth_headers(auth_token),
    )
    create_response = client.post(
        "/teams",
        json={"name": "Team O", "description": "Second team"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    update_response = client.put(
        f"/teams/{team_id}",
        json={"name": "Team N", "description": "Conflict name"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 400
    assert "already exists" in update_response.json()["detail"]


def test_list_team_members_requires_auth(client):
    response = client.get("/teams/1/members")
    assert response.status_code == 401


def test_remove_team_member_success(client, auth_token, create_user):
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


def test_remove_team_member_cannot_remove_leader(client, auth_token):
    create_response = client.post(
        "/teams",
        json={"name": "Team P", "description": "Cannot remove leader"},
        headers=auth_headers(auth_token),
    )
    team_id = create_response.json()["id"]

    remove_response = client.request(
        "DELETE",
        f"/teams/{team_id}/members",
        json={"username": "testuser"},
        headers=auth_headers(auth_token),
    )
    assert remove_response.status_code == 400
    assert "Cannot remove the team leader" in remove_response.json()["detail"]


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
