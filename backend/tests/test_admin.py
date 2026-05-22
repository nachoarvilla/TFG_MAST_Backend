import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def login(client, username: str, password: str = "password123"):
    response = client.post(
        "/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_updates_other_user_information(client, create_user):
    admin = create_user("admin_user", "admin@example.com", "password123", role="admin")
    target = create_user("normal_user", "normal@example.com", "password123")
    admin_token = login(client, admin.username)

    response = client.put(
        f"/users/{target.id}",
        json={"username": "updated_user"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "updated_user"


def test_admin_deletes_other_user(client, create_user, db_session):
    admin = create_user("delete_admin", "delete_admin@example.com", "password123", role="admin")
    target = create_user("user_to_delete", "delete_target@example.com", "password123")
    admin_token = login(client, admin.username)

    response = client.delete(
        f"/users/{target.id}",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert db_session.query(models.User).filter(models.User.id == target.id).first() is None


def test_admin_updates_team_without_membership(client, create_user):
    admin = create_user("team_admin", "team_admin@example.com", "password123", role="admin")
    leader = create_user("team_leader", "team_leader@example.com", "password123")
    leader_token = login(client, leader.username)
    admin_token = login(client, admin.username)
    create_response = client.post(
        "/teams",
        json={"name": "Admin Update Team", "description": "Original"},
        headers=auth_headers(leader_token),
    )
    team_id = create_response.json()["id"]

    response = client.put(
        f"/teams/{team_id}",
        json={"name": "Admin Updated Team", "description": "Updated by admin"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Admin Updated Team"


def test_admin_deletes_team_without_membership(client, create_user, db_session):
    admin = create_user("team_delete_admin", "team_delete_admin@example.com", "password123", role="admin")
    leader = create_user("team_delete_leader", "team_delete_leader@example.com", "password123")
    leader_token = login(client, leader.username)
    admin_token = login(client, admin.username)
    create_response = client.post(
        "/teams",
        json={"name": "Admin Delete Team", "description": "Delete target"},
        headers=auth_headers(leader_token),
    )
    team_id = create_response.json()["id"]

    response = client.delete(
        f"/teams/{team_id}",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert db_session.query(models.Team).filter(models.Team.id == team_id).first() is None


def test_admin_adds_team_member_without_membership(client, create_user):
    admin = create_user("team_member_admin", "team_member_admin@example.com", "password123", role="admin")
    leader = create_user("team_member_leader", "team_member_leader@example.com", "password123")
    new_member = create_user("team_new_member", "team_new_member@example.com", "password123")
    leader_token = login(client, leader.username)
    admin_token = login(client, admin.username)
    create_response = client.post(
        "/teams",
        json={"name": "Admin Add Member Team", "description": "Team"},
        headers=auth_headers(leader_token),
    )
    team_id = create_response.json()["id"]

    response = client.post(
        f"/teams/{team_id}/members",
        json={"username": new_member.username},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 201
    assert "added to team" in response.json()["message"]


def test_admin_removes_team_member_without_membership(client, create_user, db_session):
    admin = create_user("team_remove_admin", "team_remove_admin@example.com", "password123", role="admin")
    leader = create_user("team_remove_leader", "team_remove_leader@example.com", "password123")
    member = create_user("team_remove_member", "team_remove_member@example.com", "password123")
    team = models.Team(name="Admin Remove Member Team", description="Team")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    db_session.add(models.TeamMember(team_id=team.id, user_id=leader.id, role="leader"))
    db_session.add(models.TeamMember(team_id=team.id, user_id=member.id, role="member"))
    db_session.commit()
    admin_token = login(client, admin.username)

    response = client.request(
        "DELETE",
        f"/teams/{team.id}/members",
        json={"username": member.username},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert "removed from team" in response.json()["message"]


def test_admin_updates_project_without_membership(client, create_user, db_session):
    admin = create_user("project_admin", "project_admin@example.com", "password123", role="admin")
    owner = create_user("project_owner", "project_owner@example.com", "password123")
    project = models.Project(name="Admin Update Project", description="Original", is_private=True, owner_id=owner.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    admin_token = login(client, admin.username)

    response = client.put(
        f"/projects/{project.id}",
        json={"name": "Admin Updated Project", "description": "Updated", "is_private": False},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Admin Updated Project"


def test_admin_deletes_project_without_membership(client, create_user, db_session):
    admin = create_user("project_delete_admin", "project_delete_admin@example.com", "password123", role="admin")
    owner = create_user("project_delete_owner", "project_delete_owner@example.com", "password123")
    project = models.Project(name="Admin Delete Project", description="Delete target", is_private=True, owner_id=owner.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    admin_token = login(client, admin.username)

    response = client.delete(
        f"/projects/{project.id}",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert db_session.query(models.Project).filter(models.Project.id == project.id).first() is None


def test_admin_updates_document_uploaded_by_other_user(client, create_user, db_session):
    admin = create_user("document_admin", "document_admin@example.com", "password123", role="admin")
    uploader = create_user("document_uploader", "document_uploader@example.com", "password123")
    document = models.Document(
        name="original.pdf",
        file_path="uploads/admin-test/original.pdf",
        total_pages=1,
        description="Original",
        uploader_id=uploader.id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    admin_token = login(client, admin.username)

    response = client.put(
        f"/documents/{document.id}",
        json={"name": "updated.pdf", "description": "Updated by admin"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "updated.pdf"


def test_admin_deletes_document_uploaded_by_other_user(client, create_user, db_session):
    admin = create_user("document_delete_admin", "document_delete_admin@example.com", "password123", role="admin")
    uploader = create_user("document_delete_uploader", "document_delete_uploader@example.com", "password123")
    document = models.Document(
        name="delete.pdf",
        file_path="uploads/admin-delete/delete.pdf",
        total_pages=1,
        description="Delete target",
        uploader_id=uploader.id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    admin_token = login(client, admin.username)

    response = client.delete(
        f"/documents/{document.id}",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 204
    assert db_session.query(models.Document).filter(models.Document.id == document.id).first() is None
