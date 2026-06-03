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
