import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


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


def test_create_project_requires_auth(client):
    response = client.post(
        "/projects",
        json={"name": "Project Auth", "description": "Unauthorized"},
    )
    assert response.status_code == 401


def test_list_projects_requires_auth(client):
    response = client.get("/projects")
    assert response.status_code == 401


def test_create_project_duplicate_name(client, auth_token):
    client.post(
        "/projects",
        json={"name": "Project Duplicate", "description": "First"},
        headers=auth_headers(auth_token),
    )
    duplicate_response = client.post(
        "/projects",
        json={"name": "Project Duplicate", "description": "Second"},
        headers=auth_headers(auth_token),
    )
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"]


def test_get_project_forbidden_when_not_member(client, auth_token, create_user):
    create_response = client.post(
        "/projects",
        json={"name": "Project Private", "description": "Private project", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    outsider = create_user("outsider_proj", "outsider_proj@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    get_response = client.get(
        f"/projects/{project_id}",
        headers=auth_headers(outsider_token),
    )
    assert get_response.status_code == 403


def test_get_project_by_direct_user_access(client, auth_token, create_user, db_session):
    create_response = client.post(
        "/projects",
        json={"name": "Project User Access", "description": "Direct user access", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    collaborator = create_user("direct_collab", "direct_collab@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=collaborator.id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": collaborator.username, "password": "password123"},
    )
    collaborator_token = login_response.json()["access_token"]

    get_response = client.get(
        f"/projects/{project_id}",
        headers=auth_headers(collaborator_token),
    )
    assert get_response.status_code == 200
    assert get_response.json()["user_role"] == "collaborator"


def test_get_project_by_team_member_access(client, auth_token, create_user, db_session):
    create_response = client.post(
        "/projects",
        json={"name": "Project Team Access", "description": "Team access", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    team_member = create_user("team_member2", "team_member2@example.com", "password123")
    team_response = client.post(
        "/teams",
        json={"name": "Project Team Two", "description": "Team access 2"},
        headers=auth_headers(auth_token),
    )
    team_id = team_response.json()["id"]
    client.post(
        f"/teams/{team_id}/members",
        json={"username": team_member.username},
        headers=auth_headers(auth_token),
    )

    db_session.add(models.ProjectTeam(project_id=project_id, team_id=team_id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": team_member.username, "password": "password123"},
    )
    member_token = login_response.json()["access_token"]

    get_response = client.get(
        f"/projects/{project_id}",
        headers=auth_headers(member_token),
    )
    assert get_response.status_code == 200
    assert get_response.json()["user_role"] == "collaborator"


def test_get_project_not_found(client, auth_token):
    response = client.get(
        "/projects/9999",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404


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


def test_update_project_not_owner(client, auth_token, create_user):
    create_response = client.post(
        "/projects",
        json={"name": "Project Update Forbidden", "description": "Update by non-owner", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    outsider = create_user("outsider_proj2", "outsider_proj2@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    update_response = client.put(
        f"/projects/{project_id}",
        json={"name": "Should Fail", "description": "No access", "is_private": False},
        headers=auth_headers(outsider_token),
    )
    assert update_response.status_code == 403


def test_update_project_not_found(client, auth_token):
    response = client.put(
        "/projects/9999",
        json={"name": "No Project", "description": "Not found", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404


def test_update_project_duplicate_name(client, auth_token):
    first_response = client.post(
        "/projects",
        json={"name": "Project Existing", "description": "First project", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/projects",
        json={"name": "Project To Update", "description": "Second project", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = second_response.json()["id"]

    update_response = client.put(
        f"/projects/{project_id}",
        json={"name": "Project Existing", "description": "Conflict update", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 400
    assert "already exists" in update_response.json()["detail"]


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


def test_delete_project_not_owner(client, auth_token, create_user):
    create_response = client.post(
        "/projects",
        json={"name": "Project Delete Forbidden", "description": "Delete by non-owner", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = create_response.json()["id"]

    outsider = create_user("outsider_proj3", "outsider_proj3@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    delete_response = client.delete(
        f"/projects/{project_id}",
        headers=auth_headers(outsider_token),
    )
    assert delete_response.status_code == 403


def test_delete_project_not_found(client, auth_token):
    response = client.delete(
        "/projects/9999",
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 404


def test_list_projects_returns_owned_and_team_access(client, auth_token, create_user, db_session):
    owner_response = client.post(
        "/projects",
        json={"name": "Project Owner", "description": "Owned project", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = owner_response.json()["id"]

    team_member = create_user("team_member", "team_member@example.com", "password123")
    team_response = client.post(
        "/teams",
        json={"name": "Project Team", "description": "Team for project access"},
        headers=auth_headers(auth_token),
    )
    team_id = team_response.json()["id"]
    client.post(
        f"/teams/{team_id}/members",
        json={"username": team_member.username},
        headers=auth_headers(auth_token),
    )

    # Grant project access to the team
    db_session.add(models.ProjectTeam(project_id=project_id, team_id=team_id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": team_member.username, "password": "password123"},
    )
    member_token = login_response.json()["access_token"]

    list_response = client.get(
        "/projects",
        headers=auth_headers(member_token),
    )
    assert list_response.status_code == 200
    projects = list_response.json()["projects"]
    assert any(project["id"] == project_id for project in projects)
