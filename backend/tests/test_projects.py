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


# ========== Project User CREATE Tests ==========


def test_add_user_to_project_by_owner(client, auth_token, create_user):
    # Create project
    project_response = client.post(
        "/projects",
        json={"name": "Project Add User", "description": "Test adding user", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    # Create another user
    user_to_add = create_user("newuser1", "newuser1@example.com", "password123")

    # Add user to project
    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "newuser1", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 201
    assert "newuser1" in add_response.json()["message"]


def test_add_user_to_project_not_owner(client, auth_token, create_user):
    # Create project
    project_response = client.post(
        "/projects",
        json={"name": "Project Not Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    # Create another user and try to add
    other_user = create_user("otheruser1", "otheruser1@example.com", "password123")
    other_login = client.post(
        "/login",
        json={"username_or_email": "otheruser1", "password": "password123"},
    )
    other_token = other_login.json()["access_token"]

    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "otheruser1", "role": "viewer"},
        headers=auth_headers(other_token),
    )
    assert add_response.status_code == 403
    assert "Only the project owner can add users" in add_response.json()["detail"]


def test_add_user_to_project_user_not_found(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Fake User", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "nonexistentuser", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 404
    assert "User not found" in add_response.json()["detail"]


def test_add_user_to_project_invalid_role(client, auth_token, create_user):
    project_response = client.post(
        "/projects",
        json={"name": "Project Invalid Role", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("userinvalidrole", "userinvalidrole@example.com", "password123")

    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "userinvalidrole", "role": "admin"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 400
    assert "collaborator" in add_response.json()["detail"].lower() and "viewer" in add_response.json()["detail"].lower()


def test_add_user_to_project_already_member(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Already Member", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("alreadyuser", "alreadyuser@example.com", "password123")

    # Add first time
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "alreadyuser", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )

    # Try to add again
    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "alreadyuser", "role": "viewer"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 400
    assert "already a member" in add_response.json()["detail"]


def test_add_owner_as_member_fails(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Owner Add", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    # Get the owner username
    login_response = client.post(
        "/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    # The auth_token belongs to testuser

    add_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": "testuser", "role": "viewer"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 400
    assert "Cannot add the project owner" in add_response.json()["detail"]


def test_add_user_to_project_not_found(client, auth_token):
    add_response = client.post(
        "/projects/9999/users",
        json={"username": "someuser", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 404
    assert "Project not found" in add_response.json()["detail"]


# ========== Project User READ Tests ==========


def test_get_user_projects(client, auth_token, create_user, db_session):
    # Create project
    project_response = client.post(
        "/projects",
        json={"name": "Project Read Test", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    # Get user projects using the actual owner_id from the project
    get_response = client.get(
        f"/projects/user/{owner_id}/projects",
        headers=auth_headers(auth_token),
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert "projects" in data
    # Should have at least the project we just created
    project_names = [p["project_name"] for p in data["projects"]]
    assert "Project Read Test" in project_names


def test_get_user_projects_user_not_found(client, auth_token):
    get_response = client.get(
        "/projects/user/9999/projects",
        headers=auth_headers(auth_token),
    )
    assert get_response.status_code == 404
    assert "User not found" in get_response.json()["detail"]


def test_get_user_projects_as_different_user(client, auth_token, create_user):
    # Create project as first user
    client.post(
        "/projects",
        json={"name": "Project Different User", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )

    # Create second user
    second_user = create_user("seconduserproj", "seconduserproj@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": "seconduserproj", "password": "password123"},
    )
    second_token = login_response.json()["access_token"]

    # Get first user's projects as second user
    get_response = client.get(
        "/projects/user/1/projects",
        headers=auth_headers(second_token),
    )
    assert get_response.status_code == 200
    # Second user can see first user's projects
    assert "projects" in get_response.json()


# ========== Project User UPDATE Tests ==========


def test_update_user_role_in_project_by_owner(client, auth_token, create_user):
    # Create project and add user
    project_response = client.post(
        "/projects",
        json={"name": "Project Update Role", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("updateuser1", "updateuser1@example.com", "password123")
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "updateuser1", "role": "viewer"},
        headers=auth_headers(auth_token),
    )

    # Update role
    update_response = client.put(
        f"/projects/{project_id}/users/{user_to_add.id}",
        json={"role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 200
    assert "collaborator" in update_response.json()["message"]


def test_update_user_role_not_owner(client, auth_token, create_user):
    project_response = client.post(
        "/projects",
        json={"name": "Project Update Not Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("notowneruser", "notowneruser@example.com", "password123")
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "notowneruser", "role": "viewer"},
        headers=auth_headers(auth_token),
    )

    # Try to update as non-owner
    other_user = create_user("outsiderupdate", "outsiderupdate@example.com", "password123")
    other_login = client.post(
        "/login",
        json={"username_or_email": "outsiderupdate", "password": "password123"},
    )
    other_token = other_login.json()["access_token"]

    update_response = client.put(
        f"/projects/{project_id}/users/{user_to_add.id}",
        json={"role": "collaborator"},
        headers=auth_headers(other_token),
    )
    assert update_response.status_code == 403
    assert "Only the project owner can update user roles" in update_response.json()["detail"]


def test_update_user_role_invalid_role(client, auth_token, create_user):
    project_response = client.post(
        "/projects",
        json={"name": "Project Invalid Role Update", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("invalidroleuser", "invalidroleuser@example.com", "password123")
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "invalidroleuser", "role": "viewer"},
        headers=auth_headers(auth_token),
    )

    update_response = client.put(
        f"/projects/{project_id}/users/{user_to_add.id}",
        json={"role": "admin"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 400
    assert "collaborator" in update_response.json()["detail"].lower() and "viewer" in update_response.json()["detail"].lower()


def test_update_user_role_user_not_member(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Not Member", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    update_response = client.put(
        f"/projects/{project_id}/users/9999",
        json={"role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 404
    assert "not a member" in update_response.json()["detail"]


def test_update_owner_role_fails(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Owner Role Update", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    update_response = client.put(
        f"/projects/{project_id}/users/{owner_id}",
        json={"role": "viewer"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 400
    assert "Cannot change the project owner's role" in update_response.json()["detail"]


def test_update_user_role_project_not_found(client, auth_token):
    update_response = client.put(
        "/projects/9999/users/1",
        json={"role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert update_response.status_code == 404
    assert "Project not found" in update_response.json()["detail"]


# ========== Project User DELETE Tests ==========


def test_remove_user_from_project_by_owner(client, auth_token, create_user):
    # Create project and add user
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove User", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("removeuser1", "removeuser1@example.com", "password123")
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "removeuser1", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )

    # Remove user
    delete_response = client.delete(
        f"/projects/{project_id}/users/{user_to_add.id}",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 200
    assert "removed from project" in delete_response.json()["message"]


def test_remove_user_from_project_not_owner(client, auth_token, create_user):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Not Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    user_to_add = create_user("removeuser2", "removeuser2@example.com", "password123")
    client.post(
        f"/projects/{project_id}/users",
        json={"username": "removeuser2", "role": "viewer"},
        headers=auth_headers(auth_token),
    )

    # Try to remove as non-owner
    other_user = create_user("outsiderremove", "outsiderremove@example.com", "password123")
    other_login = client.post(
        "/login",
        json={"username_or_email": "outsiderremove", "password": "password123"},
    )
    other_token = other_login.json()["access_token"]

    delete_response = client.delete(
        f"/projects/{project_id}/users/{user_to_add.id}",
        headers=auth_headers(other_token),
    )
    assert delete_response.status_code == 403
    assert "Only the project owner can remove users" in delete_response.json()["detail"]


def test_remove_user_not_member(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Not Member", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    delete_response = client.delete(
        f"/projects/{project_id}/users/9999",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 404
    assert "not a member" in delete_response.json()["detail"]


def test_remove_owner_from_project_fails(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    delete_response = client.delete(
        f"/projects/{project_id}/users/{owner_id}",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 400
    assert "Cannot remove the project owner" in delete_response.json()["detail"]


def test_remove_user_project_not_found(client, auth_token):
    delete_response = client.delete(
        "/projects/9999/users/1",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 404
    assert "Project not found" in delete_response.json()["detail"]


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


# ========== Project Team CREATE Tests ==========


def test_add_team_to_project_by_owner(client, auth_token):
    # Create project
    project_response = client.post(
        "/projects",
        json={"name": "Project Add Team", "description": "Test adding team", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    # Create team
    team_response = client.post(
        "/teams",
        json={"name": "Team Alpha", "description": "Test team"},
        headers=auth_headers(auth_token),
    )
    team_id = team_response.json()["id"]

    # Add team to project
    add_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Team Alpha", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 201
    assert "Team Alpha" in add_response.json()["message"]
    assert add_response.json()["role"] == "collaborator"


def test_add_team_to_project_not_owner(client, auth_token, create_user):
    # Create project
    project_response = client.post(
        "/projects",
        json={"name": "Project Team Not Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    # Create team
    client.post(
        "/teams",
        json={"name": "Team Beta", "description": "Test team"},
        headers=auth_headers(auth_token),
    )

    # Try to add as non-owner
    other_user = create_user("outsiderteam", "outsiderteam@example.com", "password123")
    other_login = client.post(
        "/login",
        json={"username_or_email": "outsiderteam", "password": "password123"},
    )
    other_token = other_login.json()["access_token"]

    add_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Team Beta", "role": "viewer"},
        headers=auth_headers(other_token),
    )
    assert add_response.status_code == 403
    assert "Only the project owner can add teams" in add_response.json()["detail"]


def test_add_team_to_project_team_not_found(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Fake Team", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    add_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Nonexistent Team", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 404
    assert "Team not found" in add_response.json()["detail"]


def test_add_team_to_project_invalid_role(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Team Invalid Role", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    client.post(
        "/teams",
        json={"name": "Team Gamma", "description": "Test team"},
        headers=auth_headers(auth_token),
    )

    add_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Team Gamma", "role": "admin"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 400
    assert "collaborator" in add_response.json()["detail"].lower() and "viewer" in add_response.json()["detail"].lower()


def test_add_team_to_project_already_member(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Team Already Member", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    client.post(
        "/teams",
        json={"name": "Team Delta", "description": "Test team"},
        headers=auth_headers(auth_token),
    )

    # Add first time
    client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Team Delta", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )

    # Try to add again
    add_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Team Delta", "role": "viewer"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 400
    assert "already a member" in add_response.json()["detail"]


def test_add_team_to_project_not_found(client, auth_token):
    add_response = client.post(
        "/projects/9999/teams",
        json={"team_name": "Some Team", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_response.status_code == 404
    assert "Project not found" in add_response.json()["detail"]


# ========== Project Document CREATE Tests ==========


def test_add_document_to_project_by_owner(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Add Document", "description": "Test adding document", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="document.pdf",
        file_path="uploads/test/document.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    add_response = client.post(
        f"/projects/{project_id}/documents",
        json={"document_id": document.id},
        headers=auth_headers(auth_token),
    )

    assert add_response.status_code == 201
    data = add_response.json()
    assert data["project_id"] == project_id
    assert data["document_id"] == document.id
    assert "added to project" in data["message"]


def test_add_document_to_project_not_owner(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Document Not Owner", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="document-not-owner.pdf",
        file_path="uploads/test/document-not-owner.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    outsider = create_user("outsider_document", "outsider_document@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    add_response = client.post(
        f"/projects/{project_id}/documents",
        json={"document_id": document.id},
        headers=auth_headers(outsider_token),
    )

    assert add_response.status_code == 403
    assert "Only the project owner can add documents" in add_response.json()["detail"]


def test_add_document_to_project_document_not_found(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Missing Document", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    add_response = client.post(
        f"/projects/{project_id}/documents",
        json={"document_id": 9999},
        headers=auth_headers(auth_token),
    )

    assert add_response.status_code == 404
    assert "Document not found" in add_response.json()["detail"]


def test_add_document_to_project_already_added(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Document Duplicate", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="document-duplicate.pdf",
        file_path="uploads/test/document-duplicate.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    client.post(
        f"/projects/{project_id}/documents",
        json={"document_id": document.id},
        headers=auth_headers(auth_token),
    )
    add_response = client.post(
        f"/projects/{project_id}/documents",
        json={"document_id": document.id},
        headers=auth_headers(auth_token),
    )

    assert add_response.status_code == 400
    assert "already added" in add_response.json()["detail"]


def test_add_document_to_project_project_not_found(client, auth_token):
    add_response = client.post(
        "/projects/9999/documents",
        json={"document_id": 1},
        headers=auth_headers(auth_token),
    )

    assert add_response.status_code == 404
    assert "Project not found" in add_response.json()["detail"]


# ========== Project Document READ Tests ==========


def test_list_project_documents_returns_added_documents(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project List Documents", "description": "Test listing documents", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    first_document = models.Document(
        name="first-document.pdf",
        file_path="uploads/test/first-document.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    second_document = models.Document(
        name="second-document.pdf",
        file_path="uploads/test/second-document.pdf",
        total_pages=2,
        uploader_id=owner_id,
    )
    db_session.add_all([first_document, second_document])
    db_session.commit()
    db_session.refresh(first_document)
    db_session.refresh(second_document)

    db_session.add(models.ProjectDocument(project_id=project_id, document_id=first_document.id))
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=second_document.id))
    db_session.commit()

    list_response = client.get(
        f"/projects/{project_id}/documents",
        headers=auth_headers(auth_token),
    )

    assert list_response.status_code == 200
    data = list_response.json()
    assert data["project_id"] == project_id
    assert data["documents"] == [
        {"id": first_document.id, "name": "first-document.pdf"},
        {"id": second_document.id, "name": "second-document.pdf"},
    ]


def test_list_project_documents_allows_any_authenticated_user(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Public Document Read", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="readable-document.pdf",
        file_path="uploads/test/readable-document.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    outsider = create_user("document_reader", "document_reader@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    list_response = client.get(
        f"/projects/{project_id}/documents",
        headers=auth_headers(outsider_token),
    )

    assert list_response.status_code == 200
    assert list_response.json()["documents"] == [{"id": document.id, "name": "readable-document.pdf"}]


def test_list_project_documents_requires_auth(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Document Auth", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    list_response = client.get(f"/projects/{project_id}/documents")

    assert list_response.status_code == 401


def test_list_project_documents_project_not_found(client, auth_token):
    list_response = client.get(
        "/projects/9999/documents",
        headers=auth_headers(auth_token),
    )

    assert list_response.status_code == 404
    assert "Project not found" in list_response.json()["detail"]


# ========== Project Document DELETE Tests ==========


def test_remove_document_from_project_by_owner(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Document", "description": "Test removing document", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="remove-document.pdf",
        file_path="uploads/test/remove-document.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}",
        headers=auth_headers(auth_token),
    )

    assert delete_response.status_code == 200
    assert "removed from project" in delete_response.json()["message"]

    list_response = client.get(
        f"/projects/{project_id}/documents",
        headers=auth_headers(auth_token),
    )
    assert list_response.json()["documents"] == []


def test_remove_document_from_project_not_owner(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Document Forbidden", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="remove-forbidden.pdf",
        file_path="uploads/test/remove-forbidden.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    outsider = create_user("document_remover", "document_remover@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}",
        headers=auth_headers(outsider_token),
    )

    assert delete_response.status_code == 403
    assert "Only the project owner can remove documents" in delete_response.json()["detail"]


def test_remove_document_from_project_not_added(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Document Missing", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="not-added.pdf",
        file_path="uploads/test/not-added.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}",
        headers=auth_headers(auth_token),
    )

    assert delete_response.status_code == 404
    assert "Document is not added to this project" in delete_response.json()["detail"]


def test_remove_document_from_project_project_not_found(client, auth_token):
    delete_response = client.delete(
        "/projects/9999/documents/1",
        headers=auth_headers(auth_token),
    )

    assert delete_response.status_code == 404
    assert "Project not found" in delete_response.json()["detail"]


def test_remove_document_from_project_requires_auth(client, auth_token):
    project_response = client.post(
        "/projects",
        json={"name": "Project Remove Document Auth", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]

    delete_response = client.delete(f"/projects/{project_id}/documents/1")

    assert delete_response.status_code == 401
