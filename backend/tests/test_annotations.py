import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_create_annotation_by_project_owner(client, auth_token, db_session):
    schema_payload = {
        "name": "Annotation Schema Project",
        "type": "schema",
        "children": [
            {"name": "Highlight", "type": "annotation"},
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(f"/schemas/publish_annotation_schema/{schema_id}", headers=auth_headers(auth_token))
    assert publish_response.status_code == 201
    root_publication_id = publish_response.json()["id"]

    root_publication = db_session.query(models.SchemaPublication).filter(
        models.SchemaPublication.annotation_schema_id == schema_id,
        models.SchemaPublication.parent_id.is_(None),
    ).first()
    assert root_publication is not None
    annotation_publication = root_publication.children[0]

    project_response = client.post(
        "/projects",
        json={"name": "Project Annotation Owner", "description": "Test annotations", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": root_publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    owner_id = project_response.json()["owner_id"]
    document = models.Document(
        name="annotation-owner.pdf",
        file_path="uploads/test/annotation-owner.pdf",
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
        coordinates=[[10, 10], [20, 10], [20, 20]],
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)

    create_annotation_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}/annotations",
        json={"schema_publication_id": annotation_publication.id},
        headers=auth_headers(auth_token),
    )

    assert create_annotation_response.status_code == 201
    data = create_annotation_response.json()
    assert data["project_id"] == project_id
    assert data["document_id"] == document.id
    assert data["region_id"] == region.id
    assert data["schema_publication_id"] == annotation_publication.id
    assert data["root_schema_publication_id"] == root_publication_id

    created_annotation = db_session.query(models.Annotation).filter(models.Annotation.id == data["id"]).first()
    assert created_annotation is not None
    assert created_annotation.region_id == region.id
    assert created_annotation.schema_publication_id == annotation_publication.id
    assert created_annotation.root_schema_publication_id == root_publication_id


def test_create_annotation_forbidden_for_project_viewer(client, auth_token, create_user, db_session):
    schema_payload = {
        "name": "Annotation Schema Viewer",
        "type": "schema",
        "children": [
            {"name": "Comment", "type": "annotation"},
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(f"/schemas/publish_annotation_schema/{schema_id}", headers=auth_headers(auth_token))
    assert publish_response.status_code == 201
    root_publication_id = publish_response.json()["id"]

    root_publication = db_session.query(models.SchemaPublication).filter(
        models.SchemaPublication.annotation_schema_id == schema_id,
        models.SchemaPublication.parent_id.is_(None),
    ).first()
    assert root_publication is not None
    annotation_publication = root_publication.children[0]

    project_response = client.post(
        "/projects",
        json={"name": "Project Annotation Viewer", "description": "Test annotations", "is_private": True},
        headers=auth_headers(auth_token),
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    owner_id = project_response.json()["owner_id"]

    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": root_publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    document = models.Document(
        name="annotation-viewer.pdf",
        file_path="uploads/test/annotation-viewer.pdf",
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
        type="Rectangle",
        coordinates=[[0, 0], [10, 10]],
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)

    viewer = create_user("annotation_viewer", "annotation_viewer@example.com", "password123")
    db_session.add(models.ProjectUser(project_id=project_id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    login_response = client.post(
        "/login",
        json={"username_or_email": viewer.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    viewer_token = login_response.json()["access_token"]

    create_annotation_response = client.post(
        f"/projects/{project_id}/documents/{document.id}/regions/{region.id}/annotations",
        json={"schema_publication_id": annotation_publication.id},
        headers=auth_headers(viewer_token),
    )

    assert create_annotation_response.status_code == 403
    assert "Only project owners and collaborators can create annotations" in create_annotation_response.json()["detail"]
