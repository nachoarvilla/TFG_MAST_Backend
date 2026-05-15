import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_project_document_region(client, auth_token, db_session, project_name, is_private=True):
    project_response = client.post(
        "/projects",
        json={"name": project_name, "description": "Test reading region", "is_private": is_private},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name=f"{project_name}.pdf",
        file_path=f"uploads/test/{project_name}.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    project_document = models.ProjectDocument(project_id=project_id, document_id=document.id)
    db_session.add(project_document)
    db_session.commit()
    db_session.refresh(project_document)

    region = models.Region(
        project_document_id=project_document.id,
        page_number=1,
        type="Polygon",
        coordinates=[[1, 2], [3, 4], [5, 6]],
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)

    return project_id, document, project_document, region


def test_create_region_by_project_owner(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Owner", "description": "Test creating region", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-owner.pdf",
        file_path="uploads/test/region-owner.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Polygon",
            "coordinates": [[1, 2], [3, 4], [5, 6]],
        },
        headers=auth_headers(auth_token),
    )

    assert create_response.status_code == 201
    data = create_response.json()
    assert data["project_id"] == project_id
    assert data["document_id"] == document.id
    assert data["page_number"] == 1
    assert data["type"] == "Polygon"
    assert data["coordinates"] == [[1, 2], [3, 4], [5, 6]]


def test_create_region_by_project_collaborator(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Collaborator", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-collaborator.pdf",
        file_path="uploads/test/region-collaborator.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    collaborator = create_user("region_collab", "region_collab@example.com", "password123")
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.add(models.ProjectUser(project_id=project_id, user_id=collaborator.id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": collaborator.username, "password": "password123"},
    )
    collaborator_token = login_response.json()["access_token"]

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Rectangle",
            "coordinates": [[10, 20], [30, 40]],
        },
        headers=auth_headers(collaborator_token),
    )

    assert create_response.status_code == 201
    assert create_response.json()["type"] == "Rectangle"


def test_create_region_forbidden_for_project_viewer(client, auth_token, create_user, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Viewer", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-viewer.pdf",
        file_path="uploads/test/region-viewer.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    viewer = create_user("region_viewer", "region_viewer@example.com", "password123")
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.add(models.ProjectUser(project_id=project_id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": viewer.username, "password": "password123"},
    )
    viewer_token = login_response.json()["access_token"]

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Polyline",
            "coordinates": [[1, 1], [2, 2]],
        },
        headers=auth_headers(viewer_token),
    )

    assert create_response.status_code == 403
    assert "Only project owners and collaborators can create regions" in create_response.json()["detail"]


def test_create_region_rejects_rectangle_without_two_coordinates(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Rectangle Validation", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-rectangle-validation.pdf",
        file_path="uploads/test/region-rectangle-validation.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Rectangle",
            "coordinates": [[1, 2], [3, 4], [5, 6]],
        },
        headers=auth_headers(auth_token),
    )

    assert create_response.status_code == 400
    assert "Rectangle regions must have exactly 2 coordinates" in create_response.json()["detail"]


def test_create_region_rejects_invalid_coordinate_shape(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Invalid Coordinate", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-invalid-coordinate.pdf",
        file_path="uploads/test/region-invalid-coordinate.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Polygon",
            "coordinates": [[1, 2], [3]],
        },
        headers=auth_headers(auth_token),
    )

    assert create_response.status_code == 400
    assert "Each coordinate must be [[x, y], [x, y], ...] with numeric values" in create_response.json()["detail"]


def test_create_region_rejects_polygon_without_multiple_coordinates(client, auth_token, db_session):
    project_response = client.post(
        "/projects",
        json={"name": "Project Region Polygon Validation", "description": "Test", "is_private": True},
        headers=auth_headers(auth_token),
    )
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    document = models.Document(
        name="region-polygon-validation.pdf",
        file_path="uploads/test/region-polygon-validation.pdf",
        total_pages=1,
        uploader_id=owner_id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.add(models.ProjectDocument(project_id=project_id, document_id=document.id))
    db_session.commit()

    create_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions",
        json={
            "page_number": 1,
            "type": "Polygon",
            "coordinates": [[1, 2]],
        },
        headers=auth_headers(auth_token),
    )

    assert create_response.status_code == 400
    assert "Polygon and Polyline regions must have at least 2 coordinates" in create_response.json()["detail"]


def test_get_region_allows_private_project_user_with_any_role(client, auth_token, create_user, db_session):
    project_id, document, project_document, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Read User",
    )

    viewer = create_user("region_read_viewer", "region_read_viewer@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": viewer.username, "password": "password123"},
    )
    viewer_token = login_response.json()["access_token"]

    read_response = client.get(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        headers=auth_headers(viewer_token),
    )

    assert read_response.status_code == 200
    assert read_response.json() == {
        "project_document_id": project_document.id,
        "page_number": 1,
        "type": "Polygon",
        "coordinates": [[1, 2], [3, 4], [5, 6]],
    }


def test_get_region_allows_private_project_team_member_with_any_role(client, auth_token, create_user, db_session):
    project_id, document, project_document, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Read Team",
    )

    team_member = create_user("region_read_team", "region_read_team@example.com", "password123")
    team = models.Team(name="Region Read Team", description="Team with viewer access")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    db_session.add(models.TeamMember(user_id=team_member.id, team_id=team.id, role="member"))
    db_session.add(models.ProjectTeam(project_id=project_id, team_id=team.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": team_member.username, "password": "password123"},
    )
    team_member_token = login_response.json()["access_token"]

    read_response = client.get(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        headers=auth_headers(team_member_token),
    )

    assert read_response.status_code == 200
    assert read_response.json()["project_document_id"] == project_document.id


def test_get_region_allows_authenticated_user_for_public_project(client, auth_token, create_user, db_session):
    project_id, document, project_document, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Read Public",
        is_private=False,
    )

    reader = create_user("region_public_reader", "region_public_reader@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": reader.username, "password": "password123"},
    )
    reader_token = login_response.json()["access_token"]

    read_response = client.get(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        headers=auth_headers(reader_token),
    )

    assert read_response.status_code == 200
    assert read_response.json()["project_document_id"] == project_document.id


def test_get_region_forbidden_for_private_project_non_member(client, auth_token, create_user, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Read Forbidden",
    )

    outsider = create_user("region_private_outsider", "region_private_outsider@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": outsider.username, "password": "password123"},
    )
    outsider_token = login_response.json()["access_token"]

    read_response = client.get(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        headers=auth_headers(outsider_token),
    )

    assert read_response.status_code == 403
    assert "You don't have access to this project" in read_response.json()["detail"]


def test_update_region_by_project_owner_changes_type_and_coordinates(client, auth_token, db_session):
    project_id, document, project_document, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Update Owner",
    )

    update_response = client.put(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        json={
            "type": "Rectangle",
            "coordinates": [[10, 20], [30, 40]],
        },
        headers=auth_headers(auth_token),
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "project_document_id": project_document.id,
        "page_number": 1,
        "type": "Rectangle",
        "coordinates": [[10, 20], [30, 40]],
    }

    db_session.refresh(region)
    assert region.type == "Rectangle"
    assert region.coordinates == [[10, 20], [30, 40]]


def test_update_region_by_project_collaborator(client, auth_token, create_user, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Update Collaborator",
    )

    collaborator = create_user("region_update_collab", "region_update_collab@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=collaborator.id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": collaborator.username, "password": "password123"},
    )
    collaborator_token = login_response.json()["access_token"]

    update_response = client.put(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        json={
            "type": "Polyline",
            "coordinates": [[7, 8], [9, 10]],
        },
        headers=auth_headers(collaborator_token),
    )

    assert update_response.status_code == 200
    assert update_response.json()["type"] == "Polyline"
    assert update_response.json()["coordinates"] == [[7, 8], [9, 10]]


def test_update_region_forbidden_for_project_viewer(client, auth_token, create_user, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Update Viewer",
    )

    viewer = create_user("region_update_viewer", "region_update_viewer@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": viewer.username, "password": "password123"},
    )
    viewer_token = login_response.json()["access_token"]

    update_response = client.put(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        json={
            "type": "Polyline",
            "coordinates": [[7, 8], [9, 10]],
        },
        headers=auth_headers(viewer_token),
    )

    assert update_response.status_code == 403
    assert "Only project owners and collaborators can update regions" in update_response.json()["detail"]


def test_update_region_rejects_rectangle_without_two_coordinates(client, auth_token, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Update Rectangle Validation",
    )

    update_response = client.put(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        json={
            "type": "Rectangle",
            "coordinates": [[1, 2], [3, 4], [5, 6]],
        },
        headers=auth_headers(auth_token),
    )

    assert update_response.status_code == 400
    assert "Rectangle regions must have exactly 2 coordinates" in update_response.json()["detail"]


def test_delete_region_by_project_owner_removes_region(client, auth_token, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Delete Owner",
    )
    region_id = region.id

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}/regions/{region_id}",
        headers=auth_headers(auth_token),
    )

    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"]
    assert db_session.query(models.Region).filter(models.Region.id == region_id).first() is None


def test_delete_region_by_project_collaborator(client, auth_token, create_user, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Delete Collaborator",
    )
    region_id = region.id

    collaborator = create_user("region_delete_collab", "region_delete_collab@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=collaborator.id, role="collaborator"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": collaborator.username, "password": "password123"},
    )
    collaborator_token = login_response.json()["access_token"]

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}/regions/{region_id}",
        headers=auth_headers(collaborator_token),
    )

    assert delete_response.status_code == 200
    assert db_session.query(models.Region).filter(models.Region.id == region_id).first() is None


def test_delete_region_forbidden_for_project_viewer(client, auth_token, create_user, db_session):
    project_id, document, _, region = create_project_document_region(
        client,
        auth_token,
        db_session,
        "Project Region Delete Viewer",
    )

    viewer = create_user("region_delete_viewer", "region_delete_viewer@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": viewer.username, "password": "password123"},
    )
    viewer_token = login_response.json()["access_token"]

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}",
        headers=auth_headers(viewer_token),
    )

    assert delete_response.status_code == 403
    assert "Only project owners and collaborators can delete regions" in delete_response.json()["detail"]
    assert db_session.query(models.Region).filter(models.Region.id == region.id).first() is not None
