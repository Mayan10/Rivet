VALID_REGISTER = {"email": "projects-test@example.com", "password": "hunter22222", "accept_tos": True}


def test_create_and_list_projects(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    res = client.post("/api/v1/projects", json={"name": "My House"})
    assert res.status_code == 200
    assert res.json()["name"] == "My House"
    assert res.json()["archived_at"] is None

    res2 = client.get("/api/v1/projects")
    assert res2.status_code == 200
    assert len(res2.json()["projects"]) == 1


def test_get_project_requires_ownership(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    project_id = client.post("/api/v1/projects", json={"name": "Mine"}).json()["id"]

    client.cookies.clear()
    client.post(
        "/api/v1/auth/register", json={"email": "someone-else@example.com", "password": "hunter22222", "accept_tos": True}
    )
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 404  # not 403 -- don't reveal it exists in another org


def test_patch_project_renames(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    project_id = client.post("/api/v1/projects", json={"name": "Old Name"}).json()["id"]

    res = client.patch(f"/api/v1/projects/{project_id}", json={"name": "New Name"})
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_patch_project_archives_and_unarchives(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    project_id = client.post("/api/v1/projects", json={"name": "P"}).json()["id"]

    res = client.patch(f"/api/v1/projects/{project_id}", json={"archived": True})
    assert res.json()["archived_at"] is not None

    res2 = client.patch(f"/api/v1/projects/{project_id}", json={"archived": False})
    assert res2.json()["archived_at"] is None


def test_projects_require_authentication(client):
    res = client.get("/api/v1/projects")
    assert res.status_code == 401
