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
