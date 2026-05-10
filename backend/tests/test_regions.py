import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


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
