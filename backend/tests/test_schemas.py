import models


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_create_annotation_schema_tree(client, auth_token, db_session):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                    {"name": "Whole Column", "type": "annotation"},
                ],
            },
            {
                "name": "Panel Meaning",
                "type": "class",
                "children": [
                    {"name": "Canvas Panel", "type": "annotation"},
                ],
            },
        ],
    }

    response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["type"] == "schema"
    assert len(data["children"]) == 2
    assert data["children"][0]["type"] == "class"
    assert len(data["children"][0]["children"]) == 2

    root = db_session.query(models.AnnotationSchema).filter_by(id=data["id"]).first()
    assert root is not None
    assert root.name == payload["name"]
    assert root.user_creator_id is not None
    assert root.type == "schema"
    assert len(root.children) == 2


def test_delete_annotation_schema_tree(client, auth_token, db_session):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    publication = models.SchemaPublication(
        name="VTS: Compositional structure v1",
        type="schema",
        parent_id=None,
        annotation_schema_id=schema_id,
    )
    db_session.add(publication)
    db_session.commit()

    delete_response = client.delete(f"/schemas/{schema_id}", headers=auth_headers(auth_token))
    assert delete_response.status_code == 204

    assert db_session.query(models.AnnotationSchema).filter_by(id=schema_id).first() is None
    assert db_session.query(models.AnnotationSchema).filter(models.AnnotationSchema.parent_id == schema_id).first() is None
    assert db_session.query(models.SchemaPublication).filter_by(annotation_schema_id=schema_id).first() is None


def assert_schema_tree_matches_payload(result, expected):
    assert result["name"] == expected["name"]
    assert result["type"] == expected["type"]
    assert len(result["children"]) == len(expected.get("children", []))
    for child_result, child_expected in zip(result["children"], expected.get("children", [])):
        assert_schema_tree_matches_payload(child_result, child_expected)


def test_get_annotation_schema_tree(client, auth_token):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                    {"name": "Whole Column", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    get_response = client.get(f"/schemas/{schema_id}", headers=auth_headers(auth_token))
    assert get_response.status_code == 200

    data = get_response.json()
    assert data["id"] == schema_id
    assert_schema_tree_matches_payload(data, payload)


def test_update_annotation_schema_tree(client, auth_token, db_session):
    original_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=original_payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    updated_payload = {
        "name": "VTS: Compositional structure v2",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Column", "type": "annotation"},
                ],
            },
            {
                "name": "Panel Meaning",
                "type": "class",
                "children": [
                    {"name": "Canvas Panel", "type": "annotation"}
                ],
            },
        ],
    }

    update_response = client.put(f"/schemas/{schema_id}", json=updated_payload, headers=auth_headers(auth_token))
    assert update_response.status_code == 200

    data = update_response.json()
    assert data["id"] == schema_id
    assert data["name"] == updated_payload["name"]
    assert len(data["children"]) == 2
    assert_schema_tree_matches_payload(data, updated_payload)

    root = db_session.query(models.AnnotationSchema).filter_by(id=schema_id).first()
    assert root.name == updated_payload["name"]
    assert len(root.children) == 2


def test_publish_annotation_schema_creates_versioned_publications(client, auth_token, db_session):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    publish_response_1 = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response_1.status_code == 201
    assert publish_response_1.json()["name"].endswith(" v1")

    publish_response_2 = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response_2.status_code == 201
    assert publish_response_2.json()["name"].endswith(" v2")

    publication_roots = db_session.query(models.SchemaPublication).filter_by(annotation_schema_id=schema_id, parent_id=None).all()
    assert len(publication_roots) == 2


def test_publish_annotation_schema_requires_owner(client, auth_token, create_user):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    other_user = create_user("otheruser", "other@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    other_token = login_response.json()["access_token"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(other_token),
    )
    assert publish_response.status_code == 403


def test_get_schema_publication_tree(client, auth_token):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    get_response = client.get(f"/schemas/publications/{publication_id}", headers=auth_headers(auth_token))
    assert get_response.status_code == 200

    data = get_response.json()
    assert data["id"] == publication_id
    assert data["name"].endswith(" v1")
    assert data["type"] == "schema"
    assert len(data["children"]) == 1
    assert data["children"][0]["type"] == "class"


def test_delete_schema_publication_requires_owner(client, auth_token, create_user):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    other_user = create_user("otheruser", "other@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    other_token = login_response.json()["access_token"]

    delete_response = client.delete(
        f"/schemas/publications/{publication_id}",
        headers=auth_headers(other_token),
    )
    assert delete_response.status_code == 403


def test_delete_schema_publication_tree(client, auth_token, db_session):
    payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_response = client.post("/schemas", json=payload, headers=auth_headers(auth_token))
    assert create_response.status_code == 201
    schema_id = create_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    delete_response = client.delete(
        f"/schemas/publications/{publication_id}",
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 204

    assert db_session.query(models.SchemaPublication).filter_by(id=publication_id).first() is None
    assert db_session.query(models.SchemaPublication).filter(models.SchemaPublication.parent_id == publication_id).first() is None
    assert db_session.query(models.AnnotationSchema).filter_by(id=schema_id).first() is not None


def test_add_schema_publication_to_project(client, auth_token, db_session):
    """Test adding a schema publication to a project."""
    # Create a schema
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    # Publish the schema
    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication to the project
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201
    data = add_schema_response.json()
    assert data["project_id"] == project_id
    assert data["schema_publication_id"] == publication_id

    # Verify the association in the database
    association = db_session.query(models.ProjectSchemaPublication).filter(
        models.ProjectSchemaPublication.project_id == project_id,
        models.ProjectSchemaPublication.schema_publication_id == publication_id
    ).first()
    assert association is not None


def test_add_schema_publication_requires_owner(client, auth_token, create_user, db_session):
    """Test that only the project owner can add schema publications."""
    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Create another user
    other_user = create_user("otheruser", "other@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    other_token = login_response.json()["access_token"]

    # Try to add the schema publication as the other user
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(other_token),
    )
    assert add_schema_response.status_code == 403


def test_add_nonexistent_schema_publication(client, auth_token):
    """Test adding a non-existent schema publication."""
    # Create a project
    project_payload = {
        "name": "Test Project",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Try to add a non-existent schema publication
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": 99999},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 404


def test_add_duplicate_schema_publication(client, auth_token, db_session):
    """Test adding the same schema publication twice."""
    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication once
    add_schema_response_1 = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response_1.status_code == 201

    # Try to add it again
    add_schema_response_2 = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response_2.status_code == 409


def test_add_non_root_schema_publication(client, auth_token, db_session):
    """Test that only root schema publications can be added to a project."""
    # Create a schema with children
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    # Publish the schema
    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201

    # Get the child node id from the database
    root_publication = db_session.query(models.SchemaPublication).filter(
        models.SchemaPublication.annotation_schema_id == schema_id,
        models.SchemaPublication.parent_id.is_(None),
    ).first()
    assert root_publication is not None
    child_id = root_publication.children[0].id

    # Create a project
    project_payload = {
        "name": "Test Project",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Try to add a non-root publication (a child node)
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": child_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 400

def test_get_schema_publications_by_project(client, auth_token, db_session):
    """Test retrieving schema publications associated with a project."""
    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]
    publication_name = publish_response.json()["name"]

    # Create a project
    project_payload = {
        "name": "Test Project for Schemas",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication to the project
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    # Get the schema publications
    get_response = client.get(
        f"/projects/{project_id}/schema-publications",
        headers=auth_headers(auth_token),
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["project_id"] == project_id
    assert len(data["schema_publications"]) == 1
    assert data["schema_publications"][0]["id"] == publication_id
    assert data["schema_publications"][0]["name"] == publication_name


def test_get_schema_publications_by_project_team_member(client, auth_token, create_user, db_session):
    """Test that project team members can retrieve schema publications."""
    # Create a team
    team_response = client.post(
        "/teams",
        json={"name": "Test Team", "description": "A test team"},
        headers=auth_headers(auth_token),
    )
    assert team_response.status_code == 201
    team_id = team_response.json()["id"]

    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project for Team Schemas",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication to the project
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    # Add the team to the project
    add_team_response = client.post(
        f"/projects/{project_id}/teams",
        json={"team_name": "Test Team", "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_team_response.status_code == 201

    # Create another user and add to the team
    other_user = create_user("otheruser", "other@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    other_token = login_response.json()["access_token"]

    # Add user to team
    add_user_to_team_response = client.post(
        f"/teams/{team_id}/members",
        json={"username": other_user.username, "role": "member"},
        headers=auth_headers(auth_token),
    )
    assert add_user_to_team_response.status_code == 201

    # Other user should be able to read schema publications
    get_response = client.get(
        f"/projects/{project_id}/schema-publications",
        headers=auth_headers(other_token),
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert len(data["schema_publications"]) == 1


def test_remove_schema_publication_from_project(client, auth_token, db_session):
    """Test removing a schema publication from a project."""
    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project for Remove",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication to the project
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    # Remove the schema publication
    delete_response = client.delete(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert delete_response.status_code == 204

    # Verify the association is gone
    get_response = client.get(
        f"/projects/{project_id}/schema-publications",
        headers=auth_headers(auth_token),
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert len(data["schema_publications"]) == 0

    # Verify the schema publication still exists
    get_publication_response = client.get(
        f"/schemas/publications/{publication_id}",
        headers=auth_headers(auth_token),
    )
    assert get_publication_response.status_code == 200


def test_remove_schema_publication_requires_owner(client, auth_token, create_user):
    """Test that only the project owner can remove schema publications."""
    # Create a schema and publish it
    schema_payload = {
        "name": "VTS: Compositional structure",
        "type": "schema",
        "children": [
            {
                "name": "Panel traits",
                "type": "class",
                "children": [
                    {"name": "Whole Row", "type": "annotation"},
                ],
            }
        ],
    }

    create_schema_response = client.post("/schemas", json=schema_payload, headers=auth_headers(auth_token))
    assert create_schema_response.status_code == 201
    schema_id = create_schema_response.json()["id"]

    publish_response = client.post(
        f"/schemas/publish_annotation_schema/{schema_id}",
        headers=auth_headers(auth_token),
    )
    assert publish_response.status_code == 201
    publication_id = publish_response.json()["id"]

    # Create a project
    project_payload = {
        "name": "Test Project for Remove Auth",
        "description": "A test project",
        "is_private": True,
    }
    create_project_response = client.post("/projects", json=project_payload, headers=auth_headers(auth_token))
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    # Add the schema publication to the project
    add_schema_response = client.post(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(auth_token),
    )
    assert add_schema_response.status_code == 201

    # Create another user and add to project as collaborator
    other_user = create_user("otheruser", "other@example.com", "password123")
    login_response = client.post(
        "/login",
        json={"username_or_email": other_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    other_token = login_response.json()["access_token"]

    add_user_response = client.post(
        f"/projects/{project_id}/users",
        json={"username": other_user.username, "role": "collaborator"},
        headers=auth_headers(auth_token),
    )
    assert add_user_response.status_code == 201

    # Try to remove the schema publication as collaborator
    delete_response = client.delete(
        f"/projects/{project_id}/schema-publications",
        json={"schema_publication_id": publication_id},
        headers=auth_headers(other_token),
    )
    assert delete_response.status_code == 403